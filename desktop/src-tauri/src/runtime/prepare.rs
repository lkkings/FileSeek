//! Gets the runtime and model onto disk: the download half of the readiness flow.
//!
//! [`installed`] answers from disk alone. Only when something is missing does [`prepare`]
//! go to the network: it checks space, downloads the interpreter, the wheels and the model
//! from their sources (each checked against the sha256 compiled into the app), then
//! installs the interpreter and the wheels in one go, reporting each step.

use std::path::PathBuf;
use std::sync::atomic::AtomicBool;

use serde::{Deserialize, Serialize};

use super::download::{self, DownloadError, FileSpec, Phase, RetryPolicy};
use super::install::{self, InstallError, InsufficientSpace, Layout};
use super::manifest::{Manifest, ManifestError};

/// What the backend needs from an installed runtime.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Ready {
    pub python: PathBuf,
    pub model_cache_dir: PathBuf,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Step {
    SpaceCheck,
    Downloading,
    Verifying,
    Installing,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
pub struct Progress {
    pub step: Step,
    /// Bytes on disk across everything this run downloads, out of `total`.
    pub done: u64,
    pub total: u64,
}

#[derive(Debug)]
pub enum PrepareError {
    Manifest(ManifestError),
    Space(InsufficientSpace),
    Download(DownloadError),
    Install(InstallError),
    Io(std::io::Error),
}

impl PrepareError {
    /// The step to show as failed.
    pub fn step(&self) -> Step {
        match self {
            PrepareError::Space(_) => Step::SpaceCheck,
            PrepareError::Download(DownloadError::ChecksumMismatch { .. }) => Step::Verifying,
            PrepareError::Install(_) | PrepareError::Io(_) | PrepareError::Manifest(_) => {
                Step::Installing
            }
            PrepareError::Download(_) => Step::Downloading,
        }
    }
}

impl std::fmt::Display for PrepareError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            PrepareError::Manifest(error) => error.fmt(f),
            PrepareError::Space(space) => write!(
                f,
                "not enough disk space at {}: {} bytes needed, {} available",
                space.path.display(),
                space.required,
                space.available
            ),
            PrepareError::Download(error) => error.fmt(f),
            PrepareError::Install(error) => error.fmt(f),
            PrepareError::Io(error) => error.fmt(f),
        }
    }
}

impl std::error::Error for PrepareError {}

impl From<std::io::Error> for PrepareError {
    fn from(error: std::io::Error) -> Self {
        PrepareError::Io(error)
    }
}

#[derive(Debug, Serialize, Deserialize)]
struct CurrentModel {
    id: String,
}

fn current_model_file(layout: &Layout) -> PathBuf {
    layout.data_dir.join("models").join("current.json")
}

/// The runtime and model, if both are already installed. Reads the disk only.
pub fn installed(layout: &Layout, runtime_id: &str) -> Option<Ready> {
    let python = layout.python_path(runtime_id)?;
    let model: CurrentModel =
        serde_json::from_slice(&std::fs::read(current_model_file(layout)).ok()?).ok()?;
    layout.model_installed(&model.id).then(|| Ready {
        python,
        model_cache_dir: layout.model_dir(&model.id),
    })
}

/// Downloads and installs whatever of the runtime and model is missing.
///
/// Safe to call again after any failure: finished files are kept, partial ones resume.
pub fn prepare(
    layout: &Layout,
    manifest: &Manifest,
    retry: &RetryPolicy,
    cancel: &AtomicBool,
    on_progress: &mut dyn FnMut(Progress),
) -> Result<Ready, PrepareError> {
    let runtime_id = manifest.runtime_id.as_str();
    let need_runtime = layout.installed_runtime(runtime_id).is_none();

    let spec = |file: &str, size: u64, sha256: &str, urls: &[String]| FileSpec {
        urls: urls.to_vec(),
        dest: layout.download_path(file, sha256),
        size,
        sha256: sha256.to_owned(),
    };
    let python = &manifest.python;
    let mut runtime_specs = Vec::new();
    if need_runtime {
        runtime_specs.push(spec(&python.file, python.size, &python.sha256, &python.urls));
        for wheel in &manifest.wheels {
            runtime_specs.push(spec(&wheel.file, wheel.size, &wheel.sha256, &wheel.urls));
        }
    }
    let model_dir = layout.model_dir(&manifest.model.id);
    let model_specs: Vec<FileSpec> = if layout.model_installed(&manifest.model.id) {
        Vec::new()
    } else {
        manifest
            .model
            .files
            .iter()
            .map(|file| FileSpec {
                urls: file.urls.clone(),
                dest: model_dir.join(&file.path),
                size: file.size,
                sha256: file.sha256.clone(),
            })
            .collect()
    };

    // Space.
    on_progress(Progress {
        step: Step::SpaceCheck,
        done: 0,
        total: 0,
    });
    let remaining: u64 = runtime_specs
        .iter()
        .chain(&model_specs)
        .map(|spec| spec.size - download::bytes_present(spec))
        .sum();
    let unpacked = if need_runtime { manifest.unpacked_size } else { 0 };
    let required = install::required_space(remaining, unpacked);
    let available = install::available_space(&layout.data_dir)?;
    install::check_space(&layout.data_dir, required, available).map_err(PrepareError::Space)?;

    // Downloads, counted together so the bar moves once from 0 to the total. The model
    // goes last: it is the biggest single file, and the runtime is usable without it.
    let files: Vec<&FileSpec> = runtime_specs.iter().chain(&model_specs).collect();
    let total: u64 = files.iter().map(|spec| spec.size).sum();
    let mut finished_before = 0;
    for (index, spec) in files.iter().enumerate() {
        // Shared by both callbacks: the phase callback switches it, and every progress
        // report after that carries it.
        let step = std::cell::Cell::new(Step::Downloading);
        let last_done = std::cell::Cell::new(finished_before);
        let progress = std::cell::RefCell::new(&mut *on_progress);
        download::download_with_phases(
            spec,
            retry,
            cancel,
            &mut |bytes| {
                last_done.set(finished_before + bytes);
                (progress.borrow_mut())(Progress {
                    step: step.get(),
                    done: last_done.get(),
                    total,
                });
            },
            &mut |phase| {
                step.set(match phase {
                    Phase::Fetching => Step::Downloading,
                    Phase::Verifying => Step::Verifying,
                });
                (progress.borrow_mut())(Progress {
                    step: step.get(),
                    done: last_done.get(),
                    total,
                });
            },
        )
        .map_err(PrepareError::Download)?;
        finished_before += spec.size;

        if need_runtime && index + 1 == runtime_specs.len() {
            on_progress(Progress {
                step: Step::Installing,
                done: finished_before,
                total,
            });
            let wheels: Vec<PathBuf> = runtime_specs[1..].iter().map(|s| s.dest.clone()).collect();
            install::install_runtime(layout, runtime_id, python, &runtime_specs[0].dest, &wheels)
                .map_err(PrepareError::Install)?;
        }
    }

    if !model_specs.is_empty() {
        install::mark_model_installed(layout, &manifest.model)?;
    }
    let current = serde_json::to_vec(&CurrentModel {
        id: manifest.model.id.clone(),
    })
    .unwrap();
    std::fs::create_dir_all(model_dir.parent().unwrap())?;
    std::fs::write(current_model_file(layout), current)?;

    installed(layout, runtime_id).ok_or_else(|| {
        PrepareError::Io(std::io::Error::other(
            "runtime still not installed after preparing",
        ))
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::runtime::manifest::{ModelFile, ModelSet, PythonArchive, Wheel};
    use crate::runtime::test_server::{runtime_archive, sha256_hex, Behaviour, TestServer};

    /// A source list pointing at files served by `server`, with a mirror that has none of
    /// them listed first: every file falls through to its "official" URL.
    fn serve(server: &TestServer) -> Manifest {
        let archive = runtime_archive(true);
        let onnx = vec![7u8; 50_000];
        let tokenizer = b"{\"tokenizer\": true}".to_vec();
        server.put("official/cpython.tar.gz", archive.clone());
        server.put("official/model_quantized.onnx", onnx.clone());
        server.put("official/tokenizer.json", tokenizer.clone());
        let urls = |name: &str| vec![server.url(&format!("mirror/{name}")), server.url(&format!("official/{name}"))];

        Manifest {
            v: 2,
            runtime_id: "rt-x".into(),
            target: "test".into(),
            python: PythonArchive {
                file: "cpython.tar.gz".into(),
                size: archive.len() as u64,
                sha256: sha256_hex(&archive),
                urls: urls("cpython.tar.gz"),
                interpreter: "python/bin/python3".into(),
            },
            wheels: vec![],
            unpacked_size: 100,
            model: ModelSet {
                id: "m".into(),
                files: vec![
                    ModelFile {
                        path: "model_quantized.onnx".into(),
                        size: onnx.len() as u64,
                        sha256: sha256_hex(&onnx),
                        urls: urls("model_quantized.onnx"),
                    },
                    ModelFile {
                        path: "tokenizer/tokenizer.json".into(),
                        size: tokenizer.len() as u64,
                        sha256: sha256_hex(&tokenizer),
                        urls: urls("tokenizer.json"),
                    },
                ],
            },
        }
    }

    fn run(layout: &Layout, manifest: &Manifest, steps: &mut Vec<Progress>) -> Result<Ready, PrepareError> {
        prepare(
            layout,
            manifest,
            &RetryPolicy { backoff: vec![] },
            &AtomicBool::new(false),
            &mut |p| steps.push(p),
        )
    }

    #[test]
    fn installs_the_runtime_and_model_from_nothing() {
        let server = TestServer::start();
        let manifest = serve(&server);
        let dir = tempfile::tempdir().unwrap();
        let layout = Layout::new(dir.path().to_owned());
        assert_eq!(installed(&layout, "rt-x"), None);

        let mut steps = Vec::new();
        let ready = run(&layout, &manifest, &mut steps).unwrap();

        assert!(ready.python.ends_with("runtime/rt-x/python/bin/python3"));
        assert_eq!(ready.model_cache_dir, dir.path().join("models/m"));
        // The layout `ensure_model_cached` looks for.
        assert!(ready.model_cache_dir.join("model_quantized.onnx").is_file());
        assert!(ready.model_cache_dir.join("tokenizer/tokenizer.json").is_file());
        assert_eq!(installed(&layout, "rt-x"), Some(ready));
        assert!(!layout.downloads_dir().exists(), "downloads are cleaned up");

        let order: Vec<Step> = steps.iter().map(|p| p.step).fold(Vec::new(), |mut acc, s| {
            if acc.last() != Some(&s) {
                acc.push(s);
            }
            acc
        });
        assert_eq!(order[0], Step::SpaceCheck);
        assert!(order.contains(&Step::Verifying));
        assert!(order.contains(&Step::Installing));
        let last = steps.last().unwrap();
        assert_eq!(last.done, last.total);
    }

    #[test]
    fn a_second_run_downloads_nothing() {
        let server = TestServer::start();
        let manifest = serve(&server);
        let dir = tempfile::tempdir().unwrap();
        let layout = Layout::new(dir.path().to_owned());
        run(&layout, &manifest, &mut Vec::new()).unwrap();
        let requests = server.request_count();

        run(&layout, &manifest, &mut Vec::new()).unwrap();

        assert_eq!(server.request_count(), requests);
    }

    #[test]
    fn a_failed_run_resumes_where_it_stopped() {
        let server = TestServer::start();
        let manifest = serve(&server);
        server.set_behaviour("official/model_quantized.onnx", Behaviour::CutAfter(20_000));
        let dir = tempfile::tempdir().unwrap();
        let layout = Layout::new(dir.path().to_owned());

        let error = run(&layout, &manifest, &mut Vec::new()).unwrap_err();
        assert_eq!(error.step(), Step::Downloading);
        assert!(layout.installed_runtime("rt-x").is_some(), "the runtime got installed first");

        server.set_behaviour("official/model_quantized.onnx", Behaviour::Normal);
        run(&layout, &manifest, &mut Vec::new()).unwrap();

        assert!(server.ranges().contains(&Some(20_000)), "the model resumed from its partial file");
        assert!(installed(&layout, "rt-x").is_some());
    }

    #[cfg(unix)]
    #[test]
    fn wheels_are_downloaded_verified_and_handed_to_pip() {
        let server = TestServer::start();
        let mut manifest = serve(&server);
        let log = tempfile::tempdir().unwrap();
        let log = log.path().join("pip.log");
        let script = format!("#!/bin/sh\nfor a in \"$@\"; do last=\"$a\"; done\ncat \"$last\" > '{}'\n", log.display());
        let archive = crate::runtime::test_server::runtime_archive_with(Some(script.as_bytes()));
        server.put("official/cpython.tar.gz", archive.clone());
        manifest.python.size = archive.len() as u64;
        manifest.python.sha256 = sha256_hex(&archive);
        let wheel = b"PK wheel bytes".to_vec();
        server.put("official/demo-1.0-py3-none-any.whl", wheel.clone());
        manifest.wheels.push(Wheel {
            file: "demo-1.0-py3-none-any.whl".into(),
            size: wheel.len() as u64,
            sha256: sha256_hex(&wheel),
            urls: vec![server.url("official/demo-1.0-py3-none-any.whl")],
        });
        let dir = tempfile::tempdir().unwrap();
        let layout = Layout::new(dir.path().to_owned());

        run(&layout, &manifest, &mut Vec::new()).unwrap();

        let requirements = std::fs::read_to_string(log).unwrap();
        assert!(requirements.trim().ends_with("demo-1.0-py3-none-any.whl"), "{requirements}");
    }

    /// The real thing: this platform's interpreter and every wheel from their official
    /// sources and mirrors, verified and installed offline, then the backend imported.
    /// The model is left out (874 MB). Network access, about 425 MB on macOS; run with
    /// `cargo test --lib -- --ignored real_sources --nocapture`.
    #[test]
    #[ignore]
    fn real_sources_install_a_working_runtime() {
        let mut manifest = crate::runtime::manifest::built_in().unwrap();
        manifest.model.files.retain(|f| f.path.starts_with("tokenizer/"));
        let dir = tempfile::tempdir().unwrap();
        let layout = Layout::new(dir.path().to_owned());
        let started = std::time::Instant::now();

        let ready = prepare(
            &layout,
            &manifest,
            &RetryPolicy::default(),
            &AtomicBool::new(false),
            &mut |_| {},
        )
        .unwrap();
        eprintln!("installed in {:?}", started.elapsed());

        let backend = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../../backend/src");
        let output = std::process::Command::new(&ready.python)
            .args(["-c", "import fastapi, torch, onnxruntime, chromadb, fileseek.main; print('ok', torch.__version__)"])
            .env("PYTHONPATH", backend)
            .env("PYTHONNOUSERSITE", "1")
            .output()
            .unwrap();
        let stdout = String::from_utf8_lossy(&output.stdout);
        assert!(output.status.success(), "{stdout}{}", String::from_utf8_lossy(&output.stderr));
        eprintln!("{stdout}");
    }

    #[test]
    fn a_wheel_that_does_not_match_its_pin_is_not_installed() {
        let server = TestServer::start();
        let mut manifest = serve(&server);
        server.put("official/evil-1.0-py3-none-any.whl", b"not what was pinned".to_vec());
        manifest.wheels.push(Wheel {
            file: "evil-1.0-py3-none-any.whl".into(),
            size: 19,
            sha256: "0".repeat(64),
            urls: vec![server.url("official/evil-1.0-py3-none-any.whl")],
        });
        let dir = tempfile::tempdir().unwrap();
        let layout = Layout::new(dir.path().to_owned());

        let error = run(&layout, &manifest, &mut Vec::new()).unwrap_err();

        assert_eq!(error.step(), Step::Verifying);
        assert!(layout.installed_runtime("rt-x").is_none());
    }
}
