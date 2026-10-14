//! Where the runtime and model live on disk, and how they get there.
//!
//! ```text
//! <data_dir>/runtime/<runtime_id>/          unpacked runtime, `.complete` once usable
//! <data_dir>/runtime/.staging-<runtime_id>/ unpacking and pip happen here, then one rename
//! <data_dir>/runtime/.downloads/            interpreter archive and wheels while installing
//! <data_dir>/runtime/state.json             current and previous runtime ids
//! <data_dir>/models/<model_id>/             model files, `.complete` once all present
//! ```
//!
//! Checking whether something is installed reads `.complete` only, so an installed app
//! starts without a network connection.

use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};

use super::download::sha256_file;
use super::manifest::{ModelSet, PythonArchive};

const COMPLETE: &str = ".complete";
/// Free space beyond the computed need, so the disk is not filled to the last byte.
const SPACE_MARGIN_PERCENT: u64 = 10;

#[derive(Debug, Clone)]
pub struct Layout {
    pub data_dir: PathBuf,
}

/// What `.complete` records about an installed runtime.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct InstalledRuntime {
    pub sha256: String,
    /// Relative to the runtime directory.
    pub python: String,
}

#[derive(Debug, Default, Serialize, Deserialize)]
struct RuntimeState {
    current: Option<String>,
    previous: Option<String>,
}

#[derive(Debug, Default, Serialize, Deserialize)]
pub struct ModelState {
    pub current: Option<String>,
    pub previous: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
struct InstalledModel {
    files: Vec<(String, u64)>,
}

impl Layout {
    pub fn new(data_dir: PathBuf) -> Layout {
        Layout { data_dir }
    }

    pub fn runtimes_dir(&self) -> PathBuf {
        self.data_dir.join("runtime")
    }

    pub fn runtime_dir(&self, runtime_id: &str) -> PathBuf {
        self.runtimes_dir().join(runtime_id)
    }

    pub fn downloads_dir(&self) -> PathBuf {
        self.runtimes_dir().join(".downloads")
    }

    /// Where a downloaded file waits to be installed. Named by its sha256, so a file with
    /// the same name but other contents never passes for it.
    pub fn download_path(&self, file: &str, sha256: &str) -> PathBuf {
        let prefix = sha256.get(..16).unwrap_or(sha256);
        self.downloads_dir().join(prefix).join(file)
    }

    fn staging_dir(&self, runtime_id: &str) -> PathBuf {
        self.runtimes_dir().join(format!(".staging-{runtime_id}"))
    }

    fn state_file(&self) -> PathBuf {
        self.runtimes_dir().join("state.json")
    }

    pub fn model_dir(&self, model_id: &str) -> PathBuf {
        self.data_dir.join("models").join(model_id)
    }

    pub fn models_dir(&self) -> PathBuf {
        self.data_dir.join("models")
    }

    pub fn model_state_file(&self) -> PathBuf {
        self.models_dir().join("current.json")
    }

    /// The runtime, if it finished installing and its interpreter is still there.
    pub fn installed_runtime(&self, runtime_id: &str) -> Option<InstalledRuntime> {
        let dir = self.runtime_dir(runtime_id);
        let record: InstalledRuntime =
            serde_json::from_slice(&std::fs::read(dir.join(COMPLETE)).ok()?).ok()?;
        dir.join(&record.python).is_file().then_some(record)
    }

    pub fn python_path(&self, runtime_id: &str) -> Option<PathBuf> {
        self.installed_runtime(runtime_id)
            .map(|record| self.runtime_dir(runtime_id).join(record.python))
    }

    /// Whether every model file recorded at install time is present at its size.
    pub fn model_installed(&self, model_id: &str) -> bool {
        let dir = self.model_dir(model_id);
        let Some(record) = std::fs::read(dir.join(COMPLETE))
            .ok()
            .and_then(|bytes| serde_json::from_slice::<InstalledModel>(&bytes).ok())
        else {
            return false;
        };
        record.files.iter().all(|(path, size)| {
            std::fs::metadata(dir.join(path))
                .map(|m| m.len() == *size)
                .unwrap_or(false)
        })
    }

    /// Forgets that the runtime is installed, so the next start downloads it again.
    pub fn invalidate_runtime(&self, runtime_id: &str) -> std::io::Result<()> {
        match std::fs::remove_file(self.runtime_dir(runtime_id).join(COMPLETE)) {
            Err(error) if error.kind() != std::io::ErrorKind::NotFound => Err(error),
            _ => Ok(()),
        }
    }
}

#[derive(Debug)]
pub enum InstallError {
    Io(std::io::Error),
    /// The archive unpacked, but the interpreter the source list names is not in it.
    MissingInterpreter(String),
    /// pip could not install the wheels; the end of its output.
    Pip(String),
}

impl std::fmt::Display for InstallError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            InstallError::Io(error) => write!(f, "could not install the runtime: {error}"),
            InstallError::MissingInterpreter(path) => {
                write!(f, "the Python archive has no interpreter at {path}")
            }
            InstallError::Pip(output) => write!(f, "installing the dependencies failed: {output}"),
        }
    }
}

impl std::error::Error for InstallError {}

impl From<std::io::Error> for InstallError {
    fn from(error: std::io::Error) -> Self {
        InstallError::Io(error)
    }
}

/// Unpacks the verified interpreter archive, installs the verified wheels into it with
/// its own pip, and makes it the current runtime.
///
/// pip runs offline (`--no-index --no-deps`): it installs exactly the files given, which
/// are exactly what `uv.lock` pins, already checked against their sha256s.
///
/// Everything happens in a staging directory that is renamed into place, so an
/// interrupted install leaves either nothing or a directory without `.complete` — both of
/// which the next start treats as not installed and redoes. Keeps the previously current
/// runtime for rollback, deletes older ones, and deletes the downloads once installed.
pub fn install_runtime(
    layout: &Layout,
    runtime_id: &str,
    python: &PythonArchive,
    archive: &Path,
    wheels: &[PathBuf],
) -> Result<InstalledRuntime, InstallError> {
    let staging = layout.staging_dir(runtime_id);
    remove_dir_if_present(&staging)?;
    std::fs::create_dir_all(&staging)?;

    let decoder = flate2::read::GzDecoder::new(std::fs::File::open(archive)?);
    let mut tar = tar::Archive::new(decoder);
    tar.set_preserve_permissions(true);
    tar.unpack(&staging)?;

    let interpreter = staging.join(&python.interpreter);
    if !interpreter.is_file() {
        remove_dir_if_present(&staging)?;
        return Err(InstallError::MissingInterpreter(python.interpreter.clone()));
    }
    if !wheels.is_empty() {
        if let Err(error) = pip_install(&interpreter, &staging, wheels) {
            remove_dir_if_present(&staging)?;
            return Err(error);
        }
    }

    let dest = layout.runtime_dir(runtime_id);
    remove_dir_if_present(&dest)?;
    std::fs::rename(&staging, &dest)?;
    let record = InstalledRuntime {
        sha256: python.sha256.clone(),
        python: python.interpreter.clone(),
    };
    write_atomically(&dest.join(COMPLETE), &serde_json::to_vec(&record).unwrap())?;

    make_current(layout, runtime_id)?;
    let _ = std::fs::remove_dir_all(layout.downloads_dir());
    Ok(record)
}

/// `python -m pip install` of exactly these wheel files, isolated from whatever pip,
/// Python and configuration the user has.
fn pip_install(python: &Path, staging: &Path, wheels: &[PathBuf]) -> Result<(), InstallError> {
    // A file rather than arguments: a Windows command line would not hold 150 paths.
    let requirements = staging.join("fileseek-wheels.txt");
    let list: String = wheels
        .iter()
        .map(|w| format!("{}\n", w.display()))
        .collect();
    std::fs::write(&requirements, list)?;

    let mut command = std::process::Command::new(python);
    command
        .args([
            "-m",
            "pip",
            "install",
            "--no-index",
            "--no-deps",
            "--no-cache-dir",
        ])
        .args(["--disable-pip-version-check", "--no-warn-script-location"])
        // python-build-standalone marks itself externally managed; this copy is ours.
        .arg("--break-system-packages")
        .arg("--requirement")
        .arg(&requirements)
        .env(
            "PIP_CONFIG_FILE",
            if cfg!(windows) { "NUL" } else { "/dev/null" },
        )
        .env("PYTHONNOUSERSITE", "1")
        .env_remove("PYTHONHOME")
        .env_remove("PYTHONPATH")
        .env_remove("PIP_INDEX_URL")
        .env_remove("PIP_EXTRA_INDEX_URL")
        .env_remove("VIRTUAL_ENV")
        .stdin(std::process::Stdio::null());
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        command.creation_flags(0x0800_0000); // CREATE_NO_WINDOW
    }
    let output = command.output()?;
    let _ = std::fs::remove_file(&requirements);
    if output.status.success() {
        return Ok(());
    }
    let mut text = String::from_utf8_lossy(&output.stderr).into_owned();
    if text.trim().is_empty() {
        text = String::from_utf8_lossy(&output.stdout).into_owned();
    }
    let tail: String = text
        .chars()
        .rev()
        .take(2000)
        .collect::<Vec<_>>()
        .into_iter()
        .rev()
        .collect();
    Err(InstallError::Pip(tail.trim().to_owned()))
}

fn make_current(layout: &Layout, runtime_id: &str) -> std::io::Result<()> {
    let mut state: RuntimeState = std::fs::read(layout.state_file())
        .ok()
        .and_then(|bytes| serde_json::from_slice(&bytes).ok())
        .unwrap_or_default();
    if state.current.as_deref() != Some(runtime_id) {
        state.previous = state.current.take();
        state.current = Some(runtime_id.to_owned());
    }
    write_atomically(&layout.state_file(), &serde_json::to_vec(&state).unwrap())?;

    for entry in std::fs::read_dir(layout.runtimes_dir())?.flatten() {
        let name = entry.file_name().to_string_lossy().into_owned();
        let keep = name.starts_with('.')
            || !entry.path().is_dir()
            || Some(name.as_str()) == state.current.as_deref()
            || Some(name.as_str()) == state.previous.as_deref();
        if !keep {
            let _ = std::fs::remove_dir_all(entry.path());
        }
    }
    Ok(())
}

/// Records that every model file is in place. Call once all of them downloaded.
pub fn mark_model_installed(layout: &Layout, model: &ModelSet) -> std::io::Result<()> {
    let record = InstalledModel {
        files: model
            .files
            .iter()
            .map(|f| (f.path.clone(), f.size))
            .collect(),
    };
    write_atomically(
        &layout.model_dir(&model.id).join(COMPLETE),
        &serde_json::to_vec(&record).unwrap(),
    )
}

/// The currently selected model set, if `current.json` is readable.
pub fn current_model_id(layout: &Layout) -> Option<String> {
    let state: ModelState =
        serde_json::from_slice(&std::fs::read(layout.model_state_file()).ok()?).ok()?;
    state.current
}

/// Atomically selects a completed model set and retains one previous set for rollback.
pub fn select_model(layout: &Layout, model_id: &str) -> std::io::Result<ModelState> {
    let mut state: ModelState = std::fs::read(layout.model_state_file())
        .ok()
        .and_then(|bytes| serde_json::from_slice(&bytes).ok())
        .unwrap_or_default();
    if state.current.as_deref() != Some(model_id) {
        state.previous = state.current.take();
        state.current = Some(model_id.to_owned());
    }
    write_atomically(
        &layout.model_state_file(),
        &serde_json::to_vec(&state).unwrap(),
    )?;
    cleanup_models(layout, &state);
    Ok(state)
}

/// Makes the next start check the selected model again and replaces only files whose
/// contents no longer match the manifest.
///
/// The download step trusts files already present, so removing `.complete` alone would not
/// replace a file whose length is still correct but whose contents were damaged.
pub fn repair_model(layout: &Layout, model: &ModelSet) -> std::io::Result<()> {
    let dir = layout.model_dir(&model.id);
    remove_file_if_present(&dir.join(COMPLETE))?;
    for file in &model.files {
        let path = dir.join(&file.path);
        match sha256_file(&path) {
            Ok(sha256) if sha256.eq_ignore_ascii_case(&file.sha256) => {}
            Ok(_) => std::fs::remove_file(&path)?,
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => {}
            Err(error) => return Err(error),
        }
    }
    Ok(())
}

fn cleanup_models(layout: &Layout, state: &ModelState) {
    let Ok(entries) = std::fs::read_dir(layout.models_dir()) else {
        return;
    };
    for entry in entries.flatten() {
        let name = entry.file_name().to_string_lossy().into_owned();
        let keep = name.starts_with('.')
            || !entry.path().is_dir()
            || !entry.path().join(COMPLETE).is_file()
            || Some(name.as_str()) == state.current.as_deref()
            || Some(name.as_str()) == state.previous.as_deref();
        if !keep {
            let _ = std::fs::remove_dir_all(entry.path());
        }
    }
}

fn write_atomically(path: &Path, bytes: &[u8]) -> std::io::Result<()> {
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    let tmp = path.with_extension("tmp");
    std::fs::write(&tmp, bytes)?;
    std::fs::rename(tmp, path)
}

fn remove_file_if_present(path: &Path) -> std::io::Result<()> {
    match std::fs::remove_file(path) {
        Err(error) if error.kind() != std::io::ErrorKind::NotFound => Err(error),
        _ => Ok(()),
    }
}

fn remove_dir_if_present(path: &Path) -> std::io::Result<()> {
    match std::fs::remove_dir_all(path) {
        Err(error) if error.kind() != std::io::ErrorKind::NotFound => Err(error),
        _ => Ok(()),
    }
}

/// Free space needed under `data_dir` to finish installing, margin included.
///
/// `download_remaining` is what is still to download (interpreter, wheels, model);
/// `unpacked` the installed runtime's size, or 0 when it is installed already. Downloads
/// and the unpacked tree coexist until the downloads are deleted, so both count.
pub fn required_space(download_remaining: u64, unpacked: u64) -> u64 {
    let need = download_remaining + unpacked;
    need + need * SPACE_MARGIN_PERCENT / 100
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct InsufficientSpace {
    pub path: PathBuf,
    pub required: u64,
    pub available: u64,
}

/// Free space on the volume `path` is on (or will be on, once created).
pub fn available_space(path: &Path) -> std::io::Result<u64> {
    let existing = path
        .ancestors()
        .find(|p| p.exists())
        .unwrap_or_else(|| Path::new("/"));
    fs4::available_space(existing)
}

pub fn check_space(path: &Path, required: u64, available: u64) -> Result<(), InsufficientSpace> {
    if available >= required {
        Ok(())
    } else {
        Err(InsufficientSpace {
            path: path.to_owned(),
            required,
            available,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn python(interpreter: &str) -> PythonArchive {
        PythonArchive {
            file: "cpython.tar.gz".into(),
            size: 0,
            sha256: "abc".into(),
            urls: vec![],
            interpreter: interpreter.into(),
        }
    }

    fn make_archive(dir: &Path, with_python: bool) -> PathBuf {
        let path = dir.join("cpython.tar.gz");
        std::fs::write(
            &path,
            crate::runtime::test_server::runtime_archive(with_python),
        )
        .unwrap();
        path
    }

    /// An archive whose "interpreter" is a shell script: it records how pip was invoked
    /// (arguments, then the requirements file) and exits with `status`.
    #[cfg(unix)]
    fn archive_with_pip(dir: &Path, status: i32) -> (PathBuf, PathBuf) {
        let log = dir.join("pip.log");
        let script = format!(
            "#!/bin/sh\necho \"$@\" > '{log}'\nfor a in \"$@\"; do last=\"$a\"; done\ncat \"$last\" >> '{log}'\n[ {status} -eq 0 ] || echo 'ERROR: no space left' >&2\nexit {status}\n",
            log = log.display(),
        );
        let path = dir.join("cpython.tar.gz");
        std::fs::write(
            &path,
            crate::runtime::test_server::runtime_archive_with(Some(script.as_bytes())),
        )
        .unwrap();
        (path, log)
    }

    #[test]
    fn installs_and_reports_the_interpreter() {
        let dir = tempfile::tempdir().unwrap();
        let layout = Layout::new(dir.path().join("data"));
        let archive = make_archive(dir.path(), true);

        install_runtime(
            &layout,
            "rt-a",
            &python("python/bin/python3"),
            &archive,
            &[],
        )
        .unwrap();

        let interpreter = layout.python_path("rt-a").unwrap();
        assert!(interpreter.ends_with("rt-a/python/bin/python3"));
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            let mode = std::fs::metadata(&interpreter)
                .unwrap()
                .permissions()
                .mode();
            assert_eq!(mode & 0o111, 0o111, "interpreter keeps its execute bit");
        }
    }

    #[cfg(unix)]
    #[test]
    fn installs_exactly_the_given_wheels_offline() {
        let dir = tempfile::tempdir().unwrap();
        let layout = Layout::new(dir.path().join("data"));
        let (archive, log) = archive_with_pip(dir.path(), 0);
        let wheels = vec![
            dir.path().join("a-1-py3-none-any.whl"),
            dir.path().join("b-2-py3-none-any.whl"),
        ];
        let download = layout.download_path("x.whl", "0123456789abcdef0123");
        std::fs::create_dir_all(download.parent().unwrap()).unwrap();
        std::fs::write(&download, b"w").unwrap();

        install_runtime(
            &layout,
            "rt-a",
            &python("python/bin/python3"),
            &archive,
            &wheels,
        )
        .unwrap();

        let invocation = std::fs::read_to_string(log).unwrap();
        let args = invocation.lines().next().unwrap();
        assert!(
            args.starts_with("-m pip install --no-index --no-deps"),
            "{args}"
        );
        assert!(args.contains("--break-system-packages"));
        assert!(invocation.contains("a-1-py3-none-any.whl"));
        assert!(invocation.contains("b-2-py3-none-any.whl"));
        assert!(layout.installed_runtime("rt-a").is_some());
        assert!(!download.exists(), "downloads are deleted once installed");
    }

    #[cfg(unix)]
    #[test]
    fn a_failing_pip_leaves_nothing_installed_and_says_why() {
        let dir = tempfile::tempdir().unwrap();
        let layout = Layout::new(dir.path().join("data"));
        let (archive, _) = archive_with_pip(dir.path(), 1);

        let result = install_runtime(
            &layout,
            "rt-a",
            &python("python/bin/python3"),
            &archive,
            &[dir.path().join("a-1-py3-none-any.whl")],
        );

        match result {
            Err(InstallError::Pip(output)) => assert!(output.contains("no space left"), "{output}"),
            other => panic!("expected a pip error, got {other:?}"),
        }
        assert!(layout.installed_runtime("rt-a").is_none());
        assert!(!layout.staging_dir("rt-a").exists());
    }

    #[test]
    fn an_archive_without_the_interpreter_is_not_installed() {
        let dir = tempfile::tempdir().unwrap();
        let layout = Layout::new(dir.path().join("data"));
        let archive = make_archive(dir.path(), false);

        let result = install_runtime(
            &layout,
            "rt-a",
            &python("python/bin/python3"),
            &archive,
            &[],
        );

        assert!(matches!(result, Err(InstallError::MissingInterpreter(_))));
        assert!(layout.installed_runtime("rt-a").is_none());
    }

    #[test]
    fn an_interrupted_install_is_redone() {
        let dir = tempfile::tempdir().unwrap();
        let layout = Layout::new(dir.path().join("data"));
        // What a crash mid-install leaves: a staging dir, and a runtime dir with no marker.
        std::fs::create_dir_all(layout.staging_dir("rt-a").join("python")).unwrap();
        std::fs::create_dir_all(layout.runtime_dir("rt-a").join("python/bin")).unwrap();
        std::fs::write(
            layout.runtime_dir("rt-a").join("python/bin/python3"),
            b"half",
        )
        .unwrap();
        assert!(layout.installed_runtime("rt-a").is_none());

        let archive = make_archive(dir.path(), true);
        install_runtime(
            &layout,
            "rt-a",
            &python("python/bin/python3"),
            &archive,
            &[],
        )
        .unwrap();

        assert!(layout.installed_runtime("rt-a").is_some());
        assert!(!layout.staging_dir("rt-a").exists());
        let interpreter = std::fs::read(layout.python_path("rt-a").unwrap()).unwrap();
        assert_eq!(interpreter, b"#!/bin/sh\n");
    }

    #[test]
    fn keeps_the_previous_runtime_and_removes_older_ones() {
        let dir = tempfile::tempdir().unwrap();
        let layout = Layout::new(dir.path().join("data"));
        for id in ["rt-1", "rt-2", "rt-3"] {
            let archive = make_archive(dir.path(), true);
            install_runtime(&layout, id, &python("python/bin/python3"), &archive, &[]).unwrap();
        }

        assert!(!layout.runtime_dir("rt-1").exists());
        assert!(layout.installed_runtime("rt-2").is_some());
        assert!(layout.installed_runtime("rt-3").is_some());
    }

    #[test]
    fn a_runtime_whose_interpreter_vanished_is_not_installed() {
        let dir = tempfile::tempdir().unwrap();
        let layout = Layout::new(dir.path().join("data"));
        let archive = make_archive(dir.path(), true);
        install_runtime(
            &layout,
            "rt-a",
            &python("python/bin/python3"),
            &archive,
            &[],
        )
        .unwrap();

        std::fs::remove_file(layout.python_path("rt-a").unwrap()).unwrap();

        assert!(layout.installed_runtime("rt-a").is_none());
    }

    #[test]
    fn invalidating_forces_a_reinstall() {
        let dir = tempfile::tempdir().unwrap();
        let layout = Layout::new(dir.path().join("data"));
        let archive = make_archive(dir.path(), true);
        install_runtime(
            &layout,
            "rt-a",
            &python("python/bin/python3"),
            &archive,
            &[],
        )
        .unwrap();

        layout.invalidate_runtime("rt-a").unwrap();

        assert!(layout.installed_runtime("rt-a").is_none());
    }

    #[test]
    fn model_is_installed_only_while_every_file_is_present_at_its_size() {
        let dir = tempfile::tempdir().unwrap();
        let layout = Layout::new(dir.path().to_owned());
        let model = ModelSet {
            name: "m".into(),
            id: "m".into(),
            files: vec![super::super::manifest::ModelFile {
                path: "tokenizer/t.json".into(),
                urls: vec!["u".into()],
                size: 3,
                sha256: "s".into(),
            }],
        };
        let file = layout.model_dir("m").join("tokenizer/t.json");
        std::fs::create_dir_all(file.parent().unwrap()).unwrap();
        std::fs::write(&file, b"abc").unwrap();
        assert!(!layout.model_installed("m"), "no marker yet");

        mark_model_installed(&layout, &model).unwrap();
        assert!(layout.model_installed("m"));

        std::fs::write(&file, b"ab").unwrap();
        assert!(!layout.model_installed("m"));
    }

    #[test]
    fn space_check_counts_downloads_and_the_unpacked_runtime() {
        // backend-runtime spec: 600MB download, 1.8GB unpacked, 2.4GB free → needs ~2.64GB.
        const MB: u64 = 1_000_000;
        let required = required_space(600 * MB, 1800 * MB);
        assert_eq!(required, 2640 * MB);

        assert_eq!(
            check_space(Path::new("/data"), required, 2400 * MB),
            Err(InsufficientSpace {
                path: "/data".into(),
                required: 2640 * MB,
                available: 2400 * MB
            })
        );
        assert_eq!(
            required_space(100, 0),
            110,
            "runtime installed: only the model to fetch"
        );
    }

    #[test]
    fn downloads_are_kept_apart_by_hash() {
        let layout = Layout::new("/data".into());
        assert_ne!(
            layout.download_path("a.whl", "1111111111111111aa"),
            layout.download_path("a.whl", "2222222222222222bb")
        );
    }

    #[test]
    fn available_space_works_for_a_path_that_does_not_exist_yet() {
        let dir = tempfile::tempdir().unwrap();
        assert!(available_space(&dir.path().join("not/yet/created")).unwrap() > 0);
    }
}
