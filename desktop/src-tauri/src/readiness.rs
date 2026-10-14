//! The readiness state machine: from launch to a running backend, and keeping it running.
//!
//! ```text
//! license_check ─ unlicensed → activation ─ licensed ─┐
//!       └─ licensed ──────────────────────────────────┤
//!                                                     v
//! checking ─┬─ installed ──────────────────────────────────────→ starting → ready
//!           └─ missing → space_check → downloading → verifying → installing → starting → ready
//!              any step fails → failed (retry resumes; downloads are kept)
//! ready → backend exits → starting (restart)
//!       → two exits within 30s of starting → repair_needed (release) / failed (dev)
//! ```
//!
//! The license comes first: without one nothing is downloaded and no backend runs. A
//! license lost while running (`Command::Unlicensed`) stops the backend gracefully and
//! goes back to `activation`.
//!
//! One supervisor thread owns the state and the backend process; the UI reads the latest
//! snapshot with `get_readiness` and follows changes through the `readiness` event.

use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc::{Receiver, RecvTimeoutError, Sender};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use serde::Serialize;

use crate::runtime::download::RetryPolicy;
use crate::runtime::install::Layout;
use crate::runtime::prepare::{self, PrepareError, Progress, Step};
use crate::sidecar::{BackendCommand, Sidecar, SidecarError, SidecarFiles};

pub const EVENT_NAME: &str = "readiness";

/// Long enough for the first start on a fresh runtime, which compiles every `.pyc` it
/// imports (torch alone is thousands of modules).
const BACKEND_READY_TIMEOUT: Duration = Duration::from_secs(90);
/// A backend that dies sooner than this after starting counts as crashing on start.
const EARLY_CRASH_WINDOW: Duration = Duration::from_secs(30);
const EARLY_CRASHES_BEFORE_REPAIR: u32 = 2;
const WATCH_INTERVAL: Duration = Duration::from_secs(1);
const PROGRESS_EMIT_INTERVAL: Duration = Duration::from_millis(250);

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum State {
    LicenseCheck,
    /// No valid license: the activation screen.
    Activation,
    Checking,
    SpaceCheck,
    Downloading,
    Verifying,
    Installing,
    Starting,
    Ready,
    Failed,
    RepairNeeded,
}

impl From<Step> for State {
    fn from(step: Step) -> State {
        match step {
            Step::SpaceCheck => State::SpaceCheck,
            Step::Downloading => State::Downloading,
            Step::Verifying => State::Verifying,
            Step::Installing => State::Installing,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Snapshot {
    pub state: State,
    pub done: u64,
    pub total: u64,
    /// Bytes per second over the last few seconds, while downloading.
    pub bytes_per_second: u64,
    /// The step that failed, for `failed`.
    pub failed_step: Option<State>,
    /// What kind of failure, for the UI to word; `error` keeps the detail for the log view.
    pub error_kind: Option<ErrorKind>,
    pub error: Option<String>,
    /// For `failed` with not enough disk space.
    pub space: Option<SpaceShortfall>,
    /// For `failed` because a directory cannot be written.
    pub unwritable_path: Option<String>,
    pub log_path: Option<String>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ErrorKind {
    Network,
    /// A downloaded file did not match the sha256 pinned in the app.
    Integrity,
    DiskSpace,
    Unwritable,
    Install,
    /// The backend would not start, or kept exiting.
    Backend,
    /// No runtime package for this platform.
    Unsupported,
}

impl ErrorKind {
    fn of(error: &PrepareError) -> ErrorKind {
        use crate::runtime::download::DownloadError;
        use crate::runtime::manifest::ManifestError;
        match error {
            PrepareError::Download(DownloadError::Http(_)) => ErrorKind::Network,
            PrepareError::Download(
                DownloadError::ChecksumMismatch { .. } | DownloadError::SizeMismatch { .. },
            ) => ErrorKind::Integrity,
            PrepareError::Manifest(ManifestError::Unsupported(_)) => ErrorKind::Unsupported,
            PrepareError::Manifest(_) => ErrorKind::Integrity,
            PrepareError::Space(_) => ErrorKind::DiskSpace,
            PrepareError::Download(DownloadError::Cancelled | DownloadError::Io(_))
            | PrepareError::Io(_) => ErrorKind::Install,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SpaceShortfall {
    pub path: String,
    pub required: u64,
    pub available: u64,
}

impl Snapshot {
    fn of(state: State) -> Snapshot {
        Snapshot {
            state,
            done: 0,
            total: 0,
            bytes_per_second: 0,
            failed_step: None,
            error_kind: None,
            error: None,
            space: None,
            unwritable_path: None,
            log_path: None,
        }
    }
}

/// The list of files to download for the runtime: the one compiled into the app
/// ([`crate::runtime::manifest::built_in`]); tests point it at a local server.
pub type SourceList = Arc<
    dyn Fn() -> Result<crate::runtime::manifest::Manifest, crate::runtime::manifest::ManifestError>
        + Send
        + Sync,
>;

/// How the backend is obtained.
#[derive(Clone)]
pub enum BackendSource {
    /// Run a fixed command (debug builds: `uv run`, or `FILESEEK_BACKEND`).
    Command(BackendCommand),
    /// Download the model if needed, then run the compiled backend.
    Runtime {
        layout: Layout,
        sources: SourceList,
        backend_exe: PathBuf,
    },
}

/// Whether the app may run: the license check. May wait on the network.
pub type LicenseGate = Arc<dyn Fn() -> bool + Send + Sync>;

#[derive(Clone)]
pub struct Config {
    pub source: BackendSource,
    pub license: LicenseGate,
    pub connection_file: PathBuf,
    pub files: SidecarFiles,
    pub ready_timeout: Duration,
    pub retry: RetryPolicy,
    pub early_crash_window: Duration,
    pub watch_interval: Duration,
}

impl Config {
    pub fn new(source: BackendSource, connection_file: PathBuf, files: SidecarFiles) -> Config {
        Config {
            source,
            license: Arc::new(|| true),
            connection_file,
            files,
            ready_timeout: BACKEND_READY_TIMEOUT,
            retry: RetryPolicy::default(),
            early_crash_window: EARLY_CRASH_WINDOW,
            watch_interval: WATCH_INTERVAL,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Command {
    /// After `failed`: try again from where it stopped.
    Retry,
    /// After `repair_needed`: forget the installed runtime and install it again.
    Repair,
    /// Activated (or checked again and found valid): leave the activation screen.
    Licensed,
    /// The license is gone: stop the backend, show the activation screen.
    Unlicensed,
    Stop,
}

/// Called from the supervisor thread only, so it may keep state.
pub type Emit = Box<dyn FnMut(&Snapshot) + Send>;

/// The handle the rest of the app holds.
pub struct Readiness {
    snapshot: Arc<Mutex<Snapshot>>,
    commands: Sender<Command>,
    cancel: Arc<AtomicBool>,
    thread: Mutex<Option<std::thread::JoinHandle<()>>>,
}

impl Readiness {
    pub fn start(config: Config, emit: Emit) -> Readiness {
        let snapshot = Arc::new(Mutex::new(Snapshot::of(State::LicenseCheck)));
        let cancel = Arc::new(AtomicBool::new(false));
        let (commands, receiver) = std::sync::mpsc::channel();
        let supervisor = Supervisor {
            config,
            snapshot: snapshot.clone(),
            emit,
            cancel: cancel.clone(),
            commands: receiver,
            last_emit: None,
            rate: RateMeter::default(),
        };
        let thread = std::thread::Builder::new()
            .name("fileseek-readiness".into())
            .spawn(move || supervisor.run())
            .expect("could not start the readiness thread");
        Readiness {
            snapshot,
            commands,
            cancel,
            thread: Mutex::new(Some(thread)),
        }
    }

    pub fn snapshot(&self) -> Snapshot {
        self.snapshot.lock().unwrap().clone()
    }

    pub fn send(&self, command: Command) {
        let _ = self.commands.send(command);
    }

    /// Stops the backend and any download, waiting at most `timeout` for both.
    pub fn shutdown(&self, timeout: Duration) {
        self.cancel.store(true, Ordering::SeqCst);
        self.send(Command::Stop);
        let Some(thread) = self.thread.lock().unwrap().take() else {
            return;
        };
        let deadline = Instant::now() + timeout;
        while !thread.is_finished() && Instant::now() < deadline {
            std::thread::sleep(Duration::from_millis(50));
        }
        if thread.is_finished() {
            let _ = thread.join();
        }
    }
}

/// Download speed from the bytes seen over a sliding few seconds.
#[derive(Default)]
struct RateMeter {
    samples: std::collections::VecDeque<(Instant, u64)>,
}

impl RateMeter {
    const WINDOW: Duration = Duration::from_secs(5);

    fn record(&mut self, at: Instant, done: u64) -> u64 {
        self.samples.push_back((at, done));
        while self.samples.len() > 2 && at.duration_since(self.samples[0].0) > Self::WINDOW {
            self.samples.pop_front();
        }
        let (first_at, first_done) = self.samples[0];
        let elapsed = at.duration_since(first_at).as_secs_f64();
        if elapsed < 0.5 || done < first_done {
            return 0;
        }
        ((done - first_done) as f64 / elapsed) as u64
    }

    fn reset(&mut self) {
        self.samples.clear();
    }
}

struct Supervisor {
    config: Config,
    snapshot: Arc<Mutex<Snapshot>>,
    emit: Emit,
    cancel: Arc<AtomicBool>,
    commands: Receiver<Command>,
    last_emit: Option<(Instant, State)>,
    rate: RateMeter,
}

struct Failure {
    step: State,
    kind: ErrorKind,
    error: String,
    space: Option<SpaceShortfall>,
    unwritable_path: Option<String>,
}

impl Failure {
    fn new(step: State, kind: ErrorKind, error: String) -> Failure {
        Failure {
            step,
            kind,
            error,
            space: None,
            unwritable_path: None,
        }
    }
}

/// Whether files can be created in `dir`, creating it if needed.
fn writable(dir: &std::path::Path) -> bool {
    if std::fs::create_dir_all(dir).is_err() {
        return false;
    }
    let probe = dir.join(".fileseek-write-probe");
    let ok = std::fs::write(&probe, b"").is_ok();
    let _ = std::fs::remove_file(&probe);
    ok
}

enum Watch {
    Stopped,
    Unlicensed,
    Exited { early: bool, log_tail: String },
}

impl Supervisor {
    fn run(mut self) {
        if let BackendSource::Runtime { layout, .. } = &self.config.source {
            if let Err(error) = crate::runtime::install::remove_legacy_runtime(layout) {
                eprintln!(
                    "could not remove the old Python runtime at {}: {error}",
                    layout.legacy_runtime_dir().display()
                );
            }
        }
        let mut early_crashes = 0;
        loop {
            if !self.licensed() {
                return;
            }
            let crash_log = match self.bring_up() {
                Ok(mut sidecar) => match self.watch(&mut sidecar) {
                    Watch::Stopped => return,
                    Watch::Unlicensed => continue,
                    Watch::Exited { early: false, .. } => {
                        // Ran fine for a while, then died: just start it again.
                        early_crashes = 0;
                        continue;
                    }
                    Watch::Exited {
                        early: true,
                        log_tail,
                    } => Some(log_tail),
                },
                // Crashed while starting: counts like a crash right after start.
                Err(Some(log_tail)) => Some(log_tail),
                Err(None) => None,
            };
            if let Some(log_tail) = crash_log {
                early_crashes += 1;
                if early_crashes < EARLY_CRASHES_BEFORE_REPAIR {
                    continue;
                }
                self.crash_loop(log_tail);
            }

            // Failed: wait for the user. A command queued while working (a double click
            // on retry, say) must not count as their answer to this failure.
            // A lost license queued meanwhile is not stale: the top of the loop checks it.
            while let Ok(stale) = self.commands.try_recv() {
                match stale {
                    Command::Stop => return,
                    Command::Unlicensed => break,
                    _ => {}
                }
            }
            match self.commands.recv() {
                Ok(Command::Retry) => early_crashes = 0,
                Ok(Command::Repair) => {
                    early_crashes = 0;
                    self.repair_model();
                }
                // Back to the top, which checks the license again.
                Ok(Command::Licensed | Command::Unlicensed) => early_crashes = 0,
                Ok(Command::Stop) | Err(_) => return,
            }
        }
    }

    /// Waits until the app may run. `false` when the app is quitting.
    fn licensed(&mut self) -> bool {
        self.set(Snapshot::of(State::LicenseCheck), true);
        while !(self.config.license)() {
            self.set(Snapshot::of(State::Activation), true);
            loop {
                match self.commands.recv() {
                    Ok(Command::Licensed) => break,
                    Ok(Command::Stop) | Err(_) => return false,
                    Ok(_) => {}
                }
            }
            self.set(Snapshot::of(State::LicenseCheck), true);
        }
        true
    }

    /// Gets a backend running. `Err(Some(log))` means it started and crashed; `Err(None)`
    /// that something else failed and the state already says what.
    fn bring_up(&mut self) -> Result<Sidecar, Option<String>> {
        self.set(Snapshot::of(State::Checking), true);
        if let Some(path) = self.unwritable_dir() {
            let mut failure = Failure::new(
                State::SpaceCheck,
                ErrorKind::Unwritable,
                format!("cannot write to {}", path.display()),
            );
            failure.unwritable_path = Some(path.to_string_lossy().into_owned());
            self.fail(failure);
            return Err(None);
        }
        let command = match self.config.source.clone() {
            BackendSource::Command(command) => command,
            BackendSource::Runtime {
                layout,
                sources,
                backend_exe,
            } => {
                let ready = match prepare::installed(&layout) {
                    Some(ready) => ready,
                    None => self.download(&layout, &sources)?,
                };
                BackendCommand::production(&backend_exe, &ready.model_cache_dir)
            }
        };

        self.set(Snapshot::of(State::Starting), true);
        match Sidecar::start(
            &command,
            &self.config.connection_file,
            &self.config.files,
            self.config.ready_timeout,
            &self.cancel,
        ) {
            Ok(sidecar) => {
                println!("FileSeek backend ready on 127.0.0.1:{}", sidecar.port());
                self.set(Snapshot::of(State::Ready), true);
                Ok(sidecar)
            }
            Err(SidecarError::ExitedEarly { log_tail, .. }) => Err(Some(log_tail)),
            Err(SidecarError::Cancelled) => Err(None),
            Err(error) => {
                self.fail(Failure::new(
                    State::Starting,
                    ErrorKind::Backend,
                    error.to_string(),
                ));
                Err(None)
            }
        }
    }

    fn download(
        &mut self,
        layout: &Layout,
        sources: &SourceList,
    ) -> Result<prepare::Ready, Option<String>> {
        self.set(Snapshot::of(State::Downloading), true);
        let result = sources().map_err(PrepareError::Manifest).and_then(|manifest| {
            let cancel = self.cancel.clone();
            let retry = self.config.retry.clone();
            self.rate.reset();
            prepare::prepare(
                layout,
                &manifest,
                &retry,
                &cancel,
                &mut |progress| self.progress(progress),
            )
        });
        result.map_err(|error| {
            let mut failure = Failure::new(
                error.step().into(),
                ErrorKind::of(&error),
                error.to_string(),
            );
            if let PrepareError::Space(space) = &error {
                failure.space = Some(SpaceShortfall {
                    path: space.path.to_string_lossy().into_owned(),
                    required: space.required,
                    available: space.available,
                });
            }
            self.fail(failure);
            None
        })
    }

    /// Waits until the backend exits or the app stops it.
    fn watch(&mut self, sidecar: &mut Sidecar) -> Watch {
        loop {
            match self.commands.recv_timeout(self.config.watch_interval) {
                Ok(Command::Stop) | Err(RecvTimeoutError::Disconnected) => {
                    sidecar.stop();
                    return Watch::Stopped;
                }
                // Activation screen first, then the graceful stop: the user sees why at
                // once, and the backend still drains its queue.
                Ok(Command::Unlicensed) => {
                    self.set(Snapshot::of(State::Activation), true);
                    sidecar.stop();
                    return Watch::Unlicensed;
                }
                Ok(Command::Retry | Command::Repair | Command::Licensed)
                | Err(RecvTimeoutError::Timeout) => {}
            }
            if sidecar.exited().is_some() {
                return Watch::Exited {
                    early: sidecar.started_at().elapsed() <= self.config.early_crash_window,
                    log_tail: sidecar.log_tail(),
                };
            }
        }
    }

    fn crash_loop(&mut self, log_tail: String) {
        match self.config.source {
            BackendSource::Runtime { .. } => {
                let mut snapshot = Snapshot::of(State::RepairNeeded);
                snapshot.error_kind = Some(ErrorKind::Backend);
                snapshot.error = Some(log_tail);
                snapshot.log_path = Some(self.config.files.log.to_string_lossy().into_owned());
                self.set(snapshot, true);
            }
            // Nothing to repair when the backend is the checkout: the code is broken.
            BackendSource::Command(_) => self.fail(Failure::new(
                State::Starting,
                ErrorKind::Backend,
                format!("the backend keeps exiting on start: {log_tail}"),
            )),
        }
    }

    /// The backend is part of the signed app and cannot be repaired here; what can be is
    /// the model it loads on start. Files that no longer match their pin are deleted, so
    /// the next start downloads only those.
    fn repair_model(&self) {
        if let BackendSource::Runtime {
            layout, sources, ..
        } = &self.config.source
        {
            if let Ok(manifest) = sources() {
                let _ = crate::runtime::install::repair_model(layout, &manifest.model);
            }
        }
    }

    fn progress(&mut self, progress: Progress) {
        let mut snapshot = Snapshot::of(progress.step.into());
        snapshot.done = progress.done;
        snapshot.total = progress.total;
        snapshot.bytes_per_second = if progress.step == Step::Downloading {
            self.rate.record(Instant::now(), progress.done)
        } else {
            0
        };
        self.set(snapshot, false);
    }

    fn fail(&mut self, failure: Failure) {
        let mut snapshot = Snapshot::of(State::Failed);
        snapshot.failed_step = Some(failure.step);
        snapshot.error_kind = Some(failure.kind);
        snapshot.error = Some(failure.error);
        snapshot.space = failure.space;
        snapshot.unwritable_path = failure.unwritable_path;
        snapshot.log_path = Some(self.config.files.log.to_string_lossy().into_owned());
        self.set(snapshot, true);
    }

    /// The first directory the app needs to write to but cannot, if any.
    fn unwritable_dir(&self) -> Option<PathBuf> {
        let mut dirs = vec![self.config.files.log.parent()?.to_path_buf()];
        if let BackendSource::Runtime { layout, .. } = &self.config.source {
            dirs.push(layout.data_dir.clone());
        }
        dirs.into_iter().find(|dir| !writable(dir))
    }

    /// Records the snapshot and emits it. Progress within one state is throttled; state
    /// changes always go out.
    fn set(&mut self, snapshot: Snapshot, force: bool) {
        let now = Instant::now();
        let due = match self.last_emit {
            None => true,
            Some((at, state)) => {
                force || state != snapshot.state || now.duration_since(at) >= PROGRESS_EMIT_INTERVAL
            }
        };
        *self.snapshot.lock().unwrap() = snapshot.clone();
        if due {
            self.last_emit = Some((now, snapshot.state));
            (self.emit)(&snapshot);
        }
    }
}

/// The data directory runtimes and models are installed under: local, not roaming, on
/// Windows — a 1.4GB runtime has no business in a roaming profile.
pub fn data_dir() -> PathBuf {
    let base = dirs::data_local_dir().unwrap_or_else(|| PathBuf::from("."));
    if cfg!(any(target_os = "macos", target_os = "windows")) {
        base.join("FileSeek")
    } else {
        base.join("fileseek")
    }
}

/// The compiled backend's entry point inside its directory (`backend/build_nuitka.py`).
const BACKEND_EXE: &str = if cfg!(windows) {
    "fileseek-backend.exe"
} else {
    "fileseek-backend"
};

/// Picks how to run the backend for this build.
///
/// - `FILESEEK_BACKEND` set: that command, in any build.
/// - Debug build: `uv run` from the checkout, unless `FILESEEK_DEV_USE_RUNTIME=1` asks for
///   the release path: the backend compiled into `backend/dist/` and the model downloaded
///   from the same official sources a release build uses.
/// - Release build: the compiled backend bundled with the app, and the downloaded model.
pub fn config_for_app(resource_dir: Option<PathBuf>) -> Config {
    let connection_file = crate::preview_protocol::connection_file_path();
    let config_dir = connection_file
        .parent()
        .map(PathBuf::from)
        .unwrap_or_default();
    let files = SidecarFiles {
        log: config_dir.join("logs").join("backend.log"),
        pidfile: config_dir.join("backend.pid"),
    };

    let use_runtime =
        !cfg!(debug_assertions) || std::env::var("FILESEEK_DEV_USE_RUNTIME").as_deref() == Ok("1");
    let source = if let Some(command) = BackendCommand::from_override() {
        BackendSource::Command(command)
    } else if use_runtime {
        let backend_dir = if cfg!(debug_assertions) {
            // Unstaged in dev: what `uv run python build_nuitka.py` left in the checkout.
            repo_root()
                .join("backend")
                .join("dist")
                .join("fileseek-backend.dist")
        } else {
            resource_dir.unwrap_or_default().join("backend")
        };
        BackendSource::Runtime {
            layout: Layout::new(data_dir()),
            sources: Arc::new(crate::runtime::manifest::built_in),
            backend_exe: backend_dir.join(BACKEND_EXE),
        }
    } else {
        BackendSource::Command(BackendCommand::dev(&repo_root()))
    };
    Config::new(source, connection_file, files)
}

fn repo_root() -> PathBuf {
    std::env::current_exe()
        .ok()
        .and_then(|exe| crate::sidecar::repo_root_from_exe(&exe))
        .unwrap_or_else(|| std::env::current_dir().unwrap_or_default())
}

#[tauri::command]
pub fn get_readiness(readiness: tauri::State<'_, Readiness>) -> Snapshot {
    readiness.snapshot()
}

#[tauri::command]
pub fn retry_readiness(readiness: tauri::State<'_, Readiness>) {
    readiness.send(Command::Retry);
}

#[tauri::command]
pub fn repair_runtime(readiness: tauri::State<'_, Readiness>) {
    readiness.send(Command::Repair);
}

#[cfg(all(test, unix))]
mod tests {
    use super::*;
    use crate::runtime::manifest::{Manifest, ModelFile, ModelSet};
    use crate::runtime::test_server::{sha256_hex, Behaviour, TestServer};
    use std::path::Path;

    const FAKE_BACKEND: &str = r#"
import http.server, json, socket, sys, threading, time
# fileseek
with socket.socket() as s:
    s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({"data": {"status": "ok"}}).encode()
        self.send_response(200); self.send_header("Content-Length", str(len(body)))
        self.end_headers(); self.wfile.write(body)
    def log_message(self, *a): pass
server = http.server.HTTPServer(("127.0.0.1", port), H)
threading.Thread(target=server.serve_forever, daemon=True).start()
with open(sys.argv[1], "w") as f:
    json.dump({"port": port, "token": "t"}, f)
while True:
    time.sleep(1)
"#;

    struct Harness {
        dir: tempfile::TempDir,
        seen: Arc<Mutex<Vec<Snapshot>>>,
    }

    impl Harness {
        fn new() -> Harness {
            let dir = tempfile::tempdir().unwrap();
            std::fs::write(dir.path().join("fileseek_fake.py"), FAKE_BACKEND).unwrap();
            Harness {
                dir,
                seen: Arc::default(),
            }
        }

        fn connection_file(&self) -> PathBuf {
            self.dir.path().join("connection.json")
        }

        fn files(&self) -> SidecarFiles {
            SidecarFiles {
                log: self.dir.path().join("backend.log"),
                pidfile: self.dir.path().join("backend.pid"),
            }
        }

        fn backend_command(&self) -> BackendCommand {
            BackendCommand {
                program: "python3".into(),
                args: vec![
                    self.dir
                        .path()
                        .join("fileseek_fake.py")
                        .to_string_lossy()
                        .into_owned(),
                    self.connection_file().to_string_lossy().into_owned(),
                ],
                env: Vec::new(),
                env_remove: Vec::new(),
            }
        }

        fn config(&self, source: BackendSource) -> Config {
            let mut config = Config::new(source, self.connection_file(), self.files());
            config.ready_timeout = Duration::from_secs(15);
            config.retry = RetryPolicy { backoff: vec![] };
            config.early_crash_window = Duration::from_secs(3);
            config.watch_interval = Duration::from_millis(50);
            config
        }

        fn start(&self, config: Config) -> Readiness {
            let seen = self.seen.clone();
            Readiness::start(
                config,
                Box::new(move |s| seen.lock().unwrap().push(s.clone())),
            )
        }

        fn states(&self) -> Vec<State> {
            let mut states: Vec<State> = Vec::new();
            for snapshot in self.seen.lock().unwrap().iter() {
                if states.last() != Some(&snapshot.state) {
                    states.push(snapshot.state);
                }
            }
            states
        }

        /// Waits until the `n`th time `state` has been reached.
        fn wait_for(&self, state: State, n: usize) -> Snapshot {
            let deadline = Instant::now() + Duration::from_secs(20);
            loop {
                let hits: Vec<Snapshot> = self
                    .seen
                    .lock()
                    .unwrap()
                    .iter()
                    .filter(|s| s.state == state)
                    .cloned()
                    .collect();
                if hits.len() >= n {
                    return hits[n - 1].clone();
                }
                assert!(
                    Instant::now() < deadline,
                    "never reached {state:?} #{n}; saw {:?}",
                    self.states()
                );
                std::thread::sleep(Duration::from_millis(20));
            }
        }

        fn backend_exe(&self) -> PathBuf {
            self.dir.path().join("fileseek-backend")
        }

        /// A "compiled backend" that is a shell script running the fake backend, and a
        /// model served by `server`. With `gate`, the script exits 1 until that file exists.
        fn serve_runtime(&self, server: &TestServer, gate: Option<&Path>) -> Manifest {
            use std::os::unix::fs::PermissionsExt;
            let check = gate
                .map(|g| format!("[ -f '{}' ] || exit 1\n", g.display()))
                .unwrap_or_default();
            let script = format!(
                "#!/bin/sh\n{check}exec python3 '{}' '{}'\n",
                self.dir.path().join("fileseek_fake.py").display(),
                self.connection_file().display()
            );
            std::fs::write(self.backend_exe(), script).unwrap();
            std::fs::set_permissions(self.backend_exe(), std::fs::Permissions::from_mode(0o755))
                .unwrap();
            let model = vec![1u8; 4096];
            server.put("models/m/model_quantized.onnx", model.clone());
            Manifest {
                v: 3,
                target: "test-target".into(),
                model: ModelSet {
                    id: "m".into(),
                    files: vec![ModelFile {
                        path: "model_quantized.onnx".into(),
                        urls: vec![server.url("models/m/model_quantized.onnx")],
                        size: model.len() as u64,
                        sha256: sha256_hex(&model),
                    }],
                },
            }
        }

        fn runtime_source(&self, _server: &TestServer, manifest: Manifest) -> BackendSource {
            BackendSource::Runtime {
                layout: Layout::new(self.dir.path().join("data")),
                sources: Arc::new(move || Ok(manifest.clone())),
                backend_exe: self.backend_exe(),
            }
        }

        fn kill_backend(&self) {
            let pgid: i32 = std::fs::read_to_string(self.files().pidfile)
                .unwrap()
                .trim()
                .parse()
                .unwrap();
            // SAFETY: the group of the fake backend this test started.
            unsafe { libc::kill(-pgid, libc::SIGKILL) };
        }
    }

    #[test]
    fn dev_command_goes_straight_to_starting_and_ready() {
        let h = Harness::new();
        let readiness = h.start(h.config(BackendSource::Command(h.backend_command())));

        h.wait_for(State::Ready, 1);
        readiness.shutdown(Duration::from_secs(8));

        assert_eq!(
            h.states(),
            [State::LicenseCheck, State::Checking, State::Starting, State::Ready]
        );
        assert!(!h.files().pidfile.exists(), "backend stopped on shutdown");
    }

    #[test]
    fn without_a_license_nothing_starts_until_activation() {
        let h = Harness::new();
        let licensed = Arc::new(AtomicBool::new(false));
        let mut config = h.config(BackendSource::Command(h.backend_command()));
        config.license = {
            let licensed = licensed.clone();
            Arc::new(move || licensed.load(Ordering::SeqCst))
        };
        let readiness = h.start(config);

        h.wait_for(State::Activation, 1);
        std::thread::sleep(Duration::from_millis(200));
        assert!(!h.files().pidfile.exists(), "no backend before activation");
        assert_eq!(h.states(), [State::LicenseCheck, State::Activation]);

        licensed.store(true, Ordering::SeqCst);
        readiness.send(Command::Licensed);
        h.wait_for(State::Ready, 1);
        readiness.shutdown(Duration::from_secs(8));

        assert_eq!(
            h.states(),
            [
                State::LicenseCheck,
                State::Activation,
                State::LicenseCheck,
                State::Checking,
                State::Starting,
                State::Ready
            ]
        );
    }

    #[test]
    fn losing_the_license_stops_the_backend_and_shows_activation() {
        let h = Harness::new();
        let licensed = Arc::new(AtomicBool::new(true));
        let mut config = h.config(BackendSource::Command(h.backend_command()));
        config.license = {
            let licensed = licensed.clone();
            Arc::new(move || licensed.load(Ordering::SeqCst))
        };
        let readiness = h.start(config);
        h.wait_for(State::Ready, 1);
        let pidfile = h.files().pidfile;
        assert!(pidfile.exists());

        licensed.store(false, Ordering::SeqCst);
        readiness.send(Command::Unlicensed);
        h.wait_for(State::Activation, 1);
        let deadline = Instant::now() + Duration::from_secs(20);
        while pidfile.exists() && Instant::now() < deadline {
            std::thread::sleep(Duration::from_millis(50));
        }
        assert!(!pidfile.exists(), "the backend kept running without a license");

        // Activated again: back up.
        licensed.store(true, Ordering::SeqCst);
        readiness.send(Command::Licensed);
        h.wait_for(State::Ready, 2);
        readiness.shutdown(Duration::from_secs(8));
    }

    #[test]
    fn a_backend_that_dies_after_running_a_while_is_restarted() {
        let h = Harness::new();
        let mut config = h.config(BackendSource::Command(h.backend_command()));
        config.early_crash_window = Duration::from_millis(200);
        let readiness = h.start(config);
        h.wait_for(State::Ready, 1);
        std::thread::sleep(Duration::from_millis(400));

        h.kill_backend();

        h.wait_for(State::Ready, 2);
        assert_eq!(readiness.snapshot().state, State::Ready);
        readiness.shutdown(Duration::from_secs(8));
    }

    #[test]
    fn a_dev_backend_that_keeps_crashing_fails_instead_of_looping() {
        let h = Harness::new();
        let command = BackendCommand {
            program: "python3".into(),
            args: vec![
                "-c".into(),
                "import sys; print('ImportError: FileChunkData'); sys.exit(1)".into(),
            ],
            env: Vec::new(),
            env_remove: Vec::new(),
        };
        let readiness = h.start(h.config(BackendSource::Command(command)));

        let failed = h.wait_for(State::Failed, 1);

        assert_eq!(failed.failed_step, Some(State::Starting));
        assert!(failed.error.unwrap().contains("ImportError: FileChunkData"));
        readiness.shutdown(Duration::from_secs(8));
    }

    #[test]
    fn an_unwritable_data_dir_fails_naming_the_path() {
        let h = Harness::new();
        let server = TestServer::start();
        let manifest = h.serve_runtime(&server, None);
        // A file where the data directory should be: it can never be created.
        std::fs::write(h.dir.path().join("data"), b"").unwrap();
        let readiness = h.start(h.config(h.runtime_source(&server, manifest)));

        let failed = h.wait_for(State::Failed, 1);
        readiness.shutdown(Duration::from_secs(8));

        assert_eq!(failed.error_kind, Some(ErrorKind::Unwritable));
        assert_eq!(
            failed.unwritable_path,
            Some(h.dir.path().join("data").to_string_lossy().into_owned())
        );
        assert_eq!(server.request_count(), 0);
    }

    #[test]
    fn first_run_downloads_the_model_and_starts_the_backend() {
        let h = Harness::new();
        let server = TestServer::start();
        let manifest = h.serve_runtime(&server, None);
        let readiness = h.start(h.config(h.runtime_source(&server, manifest)));

        h.wait_for(State::Ready, 1);
        readiness.shutdown(Duration::from_secs(8));

        let states = h.states();
        for expected in [
            State::SpaceCheck,
            State::Downloading,
            State::Verifying,
            State::Installing,
            State::Starting,
        ] {
            assert!(
                states.contains(&expected),
                "missing {expected:?} in {states:?}"
            );
        }
        assert!(h
            .dir
            .path()
            .join("data/models/m/model_quantized.onnx")
            .is_file());
    }

    #[test]
    fn an_installed_model_starts_without_the_network() {
        let h = Harness::new();
        let server = TestServer::start();
        let manifest = h.serve_runtime(&server, None);
        let first = h.start(h.config(h.runtime_source(&server, manifest.clone())));
        h.wait_for(State::Ready, 1);
        first.shutdown(Duration::from_secs(8));
        let requests = server.request_count();
        h.seen.lock().unwrap().clear();

        let second = h.start(h.config(h.runtime_source(&server, manifest)));
        h.wait_for(State::Ready, 1);
        second.shutdown(Duration::from_secs(8));

        assert_eq!(server.request_count(), requests);
        assert_eq!(
            h.states(),
            [State::LicenseCheck, State::Checking, State::Starting, State::Ready]
        );
    }

    #[test]
    fn a_failed_download_waits_for_retry_and_then_resumes() {
        let h = Harness::new();
        let server = TestServer::start();
        let manifest = h.serve_runtime(&server, None);
        server.set_behaviour("models/m/model_quantized.onnx", Behaviour::CutAfter(100));
        let readiness = h.start(h.config(h.runtime_source(&server, manifest)));

        let failed = h.wait_for(State::Failed, 1);
        assert_eq!(failed.failed_step, Some(State::Downloading));
        assert_eq!(failed.error_kind, Some(ErrorKind::Network));
        assert!(failed.log_path.is_some());

        server.set_behaviour("models/m/model_quantized.onnx", Behaviour::Normal);
        readiness.send(Command::Retry);
        h.wait_for(State::Ready, 1);
        readiness.shutdown(Duration::from_secs(8));

        assert!(
            server.ranges().contains(&Some(100)),
            "retry resumed the partial download"
        );
    }

    #[test]
    fn a_backend_that_keeps_crashing_asks_for_repair_and_repair_replaces_a_damaged_model() {
        let h = Harness::new();
        let server = TestServer::start();
        let gate = h.dir.path().join("backend-is-fixed");
        let manifest = h.serve_runtime(&server, Some(&gate));
        let readiness = h.start(h.config(h.runtime_source(&server, manifest)));

        let repair = h.wait_for(State::RepairNeeded, 1);
        assert!(repair.log_path.is_some());
        // Same size, other contents: looks installed until its sha256 is checked.
        let model = h.dir.path().join("data/models/m/model_quantized.onnx");
        std::fs::write(&model, vec![2u8; 4096]).unwrap();
        let downloads = || server.ranges().len();
        let before = downloads();

        std::fs::write(&gate, b"").unwrap();
        readiness.send(Command::Repair);
        h.wait_for(State::Ready, 1);
        readiness.shutdown(Duration::from_secs(8));

        assert_eq!(downloads(), before + 1, "repair downloaded the damaged file again");
        assert_eq!(std::fs::read(&model).unwrap(), vec![1u8; 4096]);
    }

    #[test]
    fn the_old_python_runtime_is_removed_on_start() {
        let h = Harness::new();
        let server = TestServer::start();
        let manifest = h.serve_runtime(&server, None);
        let old = h.dir.path().join("data/runtime/rt-old/python/bin/python3");
        std::fs::create_dir_all(old.parent().unwrap()).unwrap();
        std::fs::write(&old, b"#!/bin/sh\n").unwrap();
        let readiness = h.start(h.config(h.runtime_source(&server, manifest)));

        h.wait_for(State::Ready, 1);
        readiness.shutdown(Duration::from_secs(8));

        assert!(!h.dir.path().join("data/runtime").exists());
    }
}

/// Decides when to tell the user the app is ready: once, after a first-run download, so
/// someone who sent the setup window to the tray learns it finished. Ordinary starts and
/// restarts stay quiet.
#[derive(Debug, Default)]
pub struct ReadyNotifier {
    downloaded: bool,
    notified: bool,
}

impl ReadyNotifier {
    /// Feed every snapshot; true when this one warrants the notification.
    pub fn observe(&mut self, state: State) -> bool {
        match state {
            State::Downloading | State::Verifying | State::Installing => self.downloaded = true,
            State::Ready if self.downloaded && !self.notified => {
                self.notified = true;
                return true;
            }
            _ => {}
        }
        false
    }
}

#[cfg(test)]
mod notifier_tests {
    use super::*;

    #[test]
    fn notifies_once_after_a_download() {
        let mut notifier = ReadyNotifier::default();
        let fired: Vec<bool> = [
            State::Checking,
            State::Downloading,
            State::Installing,
            State::Starting,
            State::Ready,
            State::Starting,
            State::Ready,
        ]
        .into_iter()
        .map(|s| notifier.observe(s))
        .collect();
        assert_eq!(fired, [false, false, false, false, true, false, false]);
    }

    #[test]
    fn a_plain_start_does_not_notify() {
        let mut notifier = ReadyNotifier::default();
        assert!(!notifier.observe(State::Checking));
        assert!(!notifier.observe(State::Starting));
        assert!(!notifier.observe(State::Ready));
    }
}
