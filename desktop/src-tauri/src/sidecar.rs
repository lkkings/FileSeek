//! Starts and stops the Python backend as a child process.
//!
//! Restored from before the front-end rewrite (`d80407a:desktop/src-tauri/src/sidecar.rs`)
//! with three changes:
//!
//! - **Production command.** Release builds run the downloaded runtime's interpreter on
//!   the backend source bundled as a resource; debug builds keep `uv run` from the
//!   checkout. `FILESEEK_BACKEND` overrides both.
//! - **Output goes to a log file**, not a pipe. Nothing reads a pipe while the backend
//!   runs, so a chatty backend would fill it and block on its next write.
//! - **Its own process group, recorded in a pidfile.** `tauri dev` kills the app outright
//!   on every rebuild, so `stop` never runs and the backend (with `uv` above it and model
//!   workers below) outlives it. The next start finds the pidfile and ends that group
//!   first, instead of leaving one more backend running per rebuild.

use std::fmt;
use std::io::{Read, Seek, SeekFrom, Write};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::time::{Duration, Instant};

const POLL_INTERVAL: Duration = Duration::from_millis(200);
/// How long a stopping backend gets before its group is killed. Must exceed the backend's
/// `task_drain_timeout` (10 s, `backend/src/fileseek/config/settings.py`) with room for the
/// rest of its shutdown: killed mid-drain, the task it was waiting for stays `processing`
/// until the next start puts it back.
pub const STOP_GRACE_PERIOD: Duration = Duration::from_secs(15);
const LOG_TAIL_BYTES: u64 = 4096;

/// A command to spawn the backend with.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct BackendCommand {
    pub program: PathBuf,
    pub args: Vec<String>,
    pub env: Vec<(String, String)>,
    /// Variables to clear, so the user's Python environment does not leak in.
    pub env_remove: Vec<String>,
}

impl BackendCommand {
    /// `FILESEEK_BACKEND`, split on whitespace into program and args: used by tests and to
    /// point a build at a backend started some other way.
    pub fn from_override() -> Option<BackendCommand> {
        let raw = std::env::var("FILESEEK_BACKEND").ok()?;
        let mut parts = raw.split_whitespace();
        let program = PathBuf::from(parts.next()?);
        Some(BackendCommand {
            program,
            args: parts.map(str::to_owned).collect(),
            env: Vec::new(),
            env_remove: Vec::new(),
        })
    }

    /// Runs the backend from the repo checkout with `uv`, as `pnpm tauri dev` does.
    pub fn dev(repo_root: &Path) -> BackendCommand {
        let backend_dir = repo_root.join("backend");
        BackendCommand {
            program: PathBuf::from("uv"),
            args: vec![
                "run".into(),
                "--directory".into(),
                backend_dir.to_string_lossy().into_owned(),
                "python".into(),
                "-m".into(),
                "fileseek".into(),
            ],
            env: Vec::new(),
            env_remove: Vec::new(),
        }
    }

    /// Runs the bundled backend source on a downloaded runtime.
    pub fn production(python: &Path, backend_src: &Path, model_cache_dir: &Path) -> BackendCommand {
        BackendCommand {
            program: python.to_owned(),
            args: vec!["-m".into(), "fileseek".into()],
            env: vec![
                (
                    "PYTHONPATH".into(),
                    backend_src.to_string_lossy().into_owned(),
                ),
                ("PYTHONNOUSERSITE".into(), "1".into()),
                ("PYTHONUTF8".into(), "1".into()),
                (
                    "EMBEDDING_MODEL_CACHE_DIR".into(),
                    model_cache_dir.to_string_lossy().into_owned(),
                ),
            ],
            env_remove: vec![
                "PYTHONHOME".into(),
                "VIRTUAL_ENV".into(),
                "PYTHONSTARTUP".into(),
            ],
        }
    }
}

/// The repo root, from the compiled binary at `<repo>/desktop/src-tauri/target/<profile>/`.
pub fn repo_root_from_exe(exe_path: &Path) -> Option<PathBuf> {
    exe_path.ancestors().nth(5).map(Path::to_path_buf)
}

#[derive(Debug)]
pub enum SidecarError {
    Spawn(std::io::Error),
    ExitedEarly {
        code: Option<i32>,
        log_tail: String,
    },
    Timeout {
        log_tail: String,
    },
    /// The app is quitting; the half-started backend has been killed.
    Cancelled,
}

impl fmt::Display for SidecarError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            SidecarError::Spawn(error) => write!(f, "could not start the backend: {error}"),
            SidecarError::ExitedEarly { code, log_tail } => write!(
                f,
                "the backend exited before it was ready (code {code:?}): {log_tail}"
            ),
            SidecarError::Timeout { log_tail } => {
                write!(f, "the backend did not become ready in time: {log_tail}")
            }
            SidecarError::Cancelled => write!(f, "cancelled"),
        }
    }
}

impl std::error::Error for SidecarError {}

/// Files the sidecar owns besides the connection file.
#[derive(Debug, Clone)]
pub struct SidecarFiles {
    /// The backend's stdout and stderr. The previous run's is kept as `<log>.1`.
    pub log: PathBuf,
    /// The process group of the backend this app last started.
    pub pidfile: PathBuf,
}

pub struct Sidecar {
    child: Child,
    port: u16,
    /// This run's token from the connection file, for `POST /shutdown`.
    token: String,
    started_at: Instant,
    files: SidecarFiles,
    log_forward_cancel: Option<Arc<AtomicBool>>,
}

impl Sidecar {
    pub fn port(&self) -> u16 {
        self.port
    }

    pub fn started_at(&self) -> Instant {
        self.started_at
    }

    /// Starts the backend and waits until it publishes its port and answers `/health`.
    ///
    /// The connection file's mtime is snapshotted before spawning so a stale file from a
    /// previous run is never mistaken for this one's.
    pub fn start(
        command: &BackendCommand,
        connection_file: &Path,
        files: &SidecarFiles,
        timeout: Duration,
        cancel: &AtomicBool,
    ) -> Result<Sidecar, SidecarError> {
        stop_stale_backend(&files.pidfile);
        let log = open_log(&files.log).map_err(SidecarError::Spawn)?;
        let previous_mtime = file_mtime(connection_file);
        let started_at = Instant::now();
        let deadline = started_at + timeout;

        let mut process = Command::new(&command.program);
        process
            .args(&command.args)
            .stdin(Stdio::null())
            .stdout(log.try_clone().map_err(SidecarError::Spawn)?)
            .stderr(log);
        for (key, value) in &command.env {
            process.env(key, value);
        }
        for key in &command.env_remove {
            process.env_remove(key);
        }
        own_process_group(&mut process);
        let mut child = process.spawn().map_err(SidecarError::Spawn)?;
        let _ = std::fs::write(&files.pidfile, child.id().to_string());

        let (port, token) = loop {
            if let Some(status) = child.try_wait().ok().flatten() {
                return Err(SidecarError::ExitedEarly {
                    code: status.code(),
                    log_tail: read_log_tail(&files.log),
                });
            }
            if cancel.load(Ordering::SeqCst) {
                kill_group(&mut child);
                let _ = std::fs::remove_file(&files.pidfile);
                return Err(SidecarError::Cancelled);
            }
            if file_mtime(connection_file) > previous_mtime {
                if let Some(connection) = crate::preview_protocol::load_connection(connection_file)
                {
                    break (connection.port, connection.token);
                }
            }
            if Instant::now() >= deadline {
                kill_group(&mut child);
                return Err(SidecarError::Timeout {
                    log_tail: read_log_tail(&files.log),
                });
            }
            std::thread::sleep(POLL_INTERVAL);
        };

        while !health_check_ok(port) {
            if let Some(status) = child.try_wait().ok().flatten() {
                return Err(SidecarError::ExitedEarly {
                    code: status.code(),
                    log_tail: read_log_tail(&files.log),
                });
            }
            if cancel.load(Ordering::SeqCst) {
                kill_group(&mut child);
                let _ = std::fs::remove_file(&files.pidfile);
                return Err(SidecarError::Cancelled);
            }
            if Instant::now() >= deadline {
                kill_group(&mut child);
                return Err(SidecarError::Timeout {
                    log_tail: read_log_tail(&files.log),
                });
            }
            std::thread::sleep(POLL_INTERVAL);
        }

        let log_forward_cancel = start_log_forwarder(&files.log);

        Ok(Sidecar {
            child,
            port,
            token,
            started_at,
            files: files.clone(),
            log_forward_cancel,
        })
    }

    /// The exit code, once the backend has exited on its own.
    pub fn exited(&mut self) -> Option<Option<i32>> {
        let status = self
            .child
            .try_wait()
            .ok()
            .flatten()
            .map(|status| status.code());
        if status.is_some() {
            self.stop_log_forwarder();
        }
        status
    }

    pub fn log_tail(&self) -> String {
        read_log_tail(&self.files.log)
    }

    /// A graceful signal to the backend first, so it drains its task queue and saves its
    /// indexes, then the whole group is killed if it does not exit in time.
    pub fn stop(&mut self) {
        self.stop_log_forwarder();
        terminate_gracefully(&mut self.child, self.port, &self.token);
        let deadline = Instant::now() + STOP_GRACE_PERIOD;
        while Instant::now() < deadline {
            if matches!(self.child.try_wait(), Ok(Some(_))) {
                break;
            }
            std::thread::sleep(POLL_INTERVAL);
        }
        // Even after a clean exit: model workers in the group may still be winding down.
        kill_group(&mut self.child);
        let _ = std::fs::remove_file(&self.files.pidfile);
    }

    fn stop_log_forwarder(&self) {
        if let Some(cancel) = &self.log_forward_cancel {
            cancel.store(true, Ordering::SeqCst);
        }
    }
}

impl Drop for Sidecar {
    fn drop(&mut self) {
        if matches!(self.child.try_wait(), Ok(None)) {
            self.stop();
        }
    }
}

fn open_log(path: &Path) -> std::io::Result<std::fs::File> {
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    if path.exists() {
        let mut previous = path.as_os_str().to_owned();
        previous.push(".1");
        let _ = std::fs::rename(path, PathBuf::from(previous));
    }
    std::fs::File::create(path)
}

/// The end of the backend's log, for a readable failure message.
pub fn read_log_tail(path: &Path) -> String {
    let Ok(mut file) = std::fs::File::open(path) else {
        return String::new();
    };
    let len = file.metadata().map(|m| m.len()).unwrap_or(0);
    let _ = file.seek(SeekFrom::Start(len.saturating_sub(LOG_TAIL_BYTES)));
    let mut buffer = Vec::new();
    let _ = file.read_to_end(&mut buffer);
    String::from_utf8_lossy(&buffer).into_owned()
}

fn start_log_forwarder(path: &Path) -> Option<Arc<AtomicBool>> {
    if !cfg!(debug_assertions)
        || std::env::var("FILESEEK_BACKEND_LOG_TO_TERMINAL").as_deref() == Ok("0")
    {
        return None;
    }

    let path = path.to_path_buf();
    let cancel = Arc::new(AtomicBool::new(false));
    let thread_cancel = cancel.clone();
    let spawned = std::thread::Builder::new()
        .name("fileseek-backend-log".into())
        .spawn(move || {
            println!("FileSeek backend log: {}", path.to_string_lossy());
            let Ok(mut file) = std::fs::File::open(&path) else {
                return;
            };
            let mut position = 0u64;
            let mut buffer = Vec::new();
            loop {
                if thread_cancel.load(Ordering::SeqCst) {
                    break;
                }
                let len = file.metadata().map(|meta| meta.len()).unwrap_or(position);
                if len < position {
                    break;
                }
                if len > position {
                    let read_len = (len - position) as usize;
                    buffer.resize(read_len, 0);
                    if file
                        .seek(SeekFrom::Start(position))
                        .and_then(|_| file.read_exact(&mut buffer))
                        .is_err()
                    {
                        break;
                    }
                    let _ = std::io::stdout().write_all(&buffer);
                    let _ = std::io::stdout().flush();
                    position = len;
                    continue;
                }
                std::thread::sleep(POLL_INTERVAL);
            }
        });

    spawned.is_ok().then_some(cancel)
}

fn file_mtime(path: &Path) -> Option<std::time::SystemTime> {
    std::fs::metadata(path)
        .and_then(|meta| meta.modified())
        .ok()
}

pub fn health_check_ok(port: u16) -> bool {
    let url = format!("http://127.0.0.1:{port}/health");
    let Ok(response) = ureq::get(&url).timeout(Duration::from_secs(1)).call() else {
        return false;
    };
    let Ok(body) = response.into_json::<serde_json::Value>() else {
        return false;
    };
    body.pointer("/data/status").and_then(|s| s.as_str()) == Some("ok")
}

#[cfg(unix)]
fn own_process_group(command: &mut Command) {
    use std::os::unix::process::CommandExt;
    command.process_group(0);
}

#[cfg(windows)]
fn own_process_group(command: &mut Command) {
    use std::os::windows::process::CommandExt;
    // No console window for the backend; a release build is a GUI app.
    const CREATE_NO_WINDOW: u32 = 0x0800_0000;
    command.creation_flags(CREATE_NO_WINDOW);
}

#[cfg(unix)]
fn terminate_gracefully(child: &mut Child, _port: u16, _token: &str) {
    // SAFETY: signalling a pid this process spawned.
    unsafe {
        libc::kill(child.id() as libc::pid_t, libc::SIGTERM);
    }
}

/// No SIGTERM on Windows, and killing outright skips the backend's shutdown: the task it
/// is computing stays `processing` and the connection file is left behind. Ask it to stop
/// instead; if it cannot be asked, `stop` kills it once the grace period runs out.
#[cfg(not(unix))]
fn terminate_gracefully(_child: &mut Child, port: u16, token: &str) {
    // Nothing to do on failure: `stop` kills the group when the grace period runs out.
    let _ = request_shutdown(port, token);
}

/// `POST /shutdown` with this run's token. True once the backend has agreed to stop.
#[cfg_attr(unix, allow(dead_code))] // Unix stops the backend with SIGTERM.
pub fn request_shutdown(port: u16, token: &str) -> bool {
    let url = format!("http://127.0.0.1:{port}/shutdown");
    ureq::post(&url)
        .set("X-FileSeek-Token", token)
        .timeout(Duration::from_secs(2))
        .call()
        .is_ok()
}

#[cfg(unix)]
fn kill_group(child: &mut Child) {
    // SAFETY: the child leads its own group (`process_group(0)`), so its pid is the pgid.
    unsafe {
        libc::kill(-(child.id() as libc::pid_t), libc::SIGKILL);
    }
    let _ = child.wait();
}

#[cfg(not(unix))]
fn kill_group(child: &mut Child) {
    let _ = child.kill();
    let _ = child.wait();
}

/// Ends the backend a previous run of this app left behind, if one is still running.
///
/// Kills the group only if something in it is still a FileSeek process, so a pid that has
/// since been reused by an unrelated program is left alone.
#[cfg(unix)]
fn stop_stale_backend(pidfile: &Path) {
    let Some(pgid) = std::fs::read_to_string(pidfile)
        .ok()
        .and_then(|text| text.trim().parse::<i32>().ok())
        .filter(|pgid| *pgid > 1)
    else {
        return;
    };
    let ours = Command::new("pgrep")
        .args(["-g", &pgid.to_string(), "-f", "fileseek"])
        .stdout(Stdio::null())
        .status()
        .map(|status| status.success())
        .unwrap_or(false);
    if ours {
        // SAFETY: signalling a process group verified above to be a FileSeek backend.
        unsafe {
            libc::kill(-pgid, libc::SIGTERM);
        }
        let deadline = Instant::now() + STOP_GRACE_PERIOD;
        while Instant::now() < deadline && group_alive(pgid) {
            std::thread::sleep(POLL_INTERVAL);
        }
        // SAFETY: as above.
        unsafe {
            libc::kill(-pgid, libc::SIGKILL);
        }
    }
    let _ = std::fs::remove_file(pidfile);
}

#[cfg(unix)]
fn group_alive(pgid: i32) -> bool {
    // SAFETY: signal 0 only checks whether the group exists.
    unsafe { libc::kill(-pgid, 0) == 0 }
}

#[cfg(not(unix))]
fn stop_stale_backend(pidfile: &Path) {
    // Without process groups there is no safe way to tell a leftover backend from a reused
    // pid; a leftover only costs memory until the user logs out.
    let _ = std::fs::remove_file(pidfile);
}

#[cfg(test)]
mod tests {
    use super::*;

    /// A stand-in backend: writes a connection file, then answers `/health`. Takes the
    /// connection file path and, optionally, a child to spawn into its group (to stand in
    /// for a model worker).
    const FAKE_BACKEND_SCRIPT: &str = r#"
import http.server, json, os, socket, subprocess, sys, threading, time
# fileseek: the marker stop_stale_backend looks for in the command line.
with socket.socket() as s:
    s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({"data": {"status": "ok"}}).encode()
        self.send_response(200); self.send_header("Content-Length", str(len(body)))
        self.end_headers(); self.wfile.write(body)
    def do_POST(self):
        ok = self.path == "/shutdown" and self.headers.get("X-FileSeek-Token") == "t"
        self.send_response(200 if ok else 401); self.send_header("Content-Length", "0")
        self.end_headers()
        if ok:
            threading.Timer(0.2, lambda: os._exit(0)).start()
    def log_message(self, *a): pass
server = http.server.HTTPServer(("127.0.0.1", port), H)
threading.Thread(target=server.serve_forever, daemon=True).start()
if len(sys.argv) > 2 and sys.argv[2] == "spawn-worker":
    subprocess.Popen([sys.executable, "-c", "import time; time.sleep(600)", "fileseek-worker"])
if len(sys.argv) > 3 and sys.argv[2] == "slow-drain":
    # Stands in for a backend still draining its task queue: exits a while after SIGTERM,
    # leaving a marker that it got to finish.
    import signal
    def drain(*_):
        time.sleep(float(sys.argv[4]))
        open(sys.argv[3], "w").close()
        sys.exit(0)
    signal.signal(signal.SIGTERM, drain)
print("backend output", flush=True)
with open(sys.argv[1], "w") as f:
    json.dump({"port": port, "token": "t"}, f)
while True:
    time.sleep(1)
"#;

    struct Fixture {
        dir: tempfile::TempDir,
    }

    impl Fixture {
        fn new() -> Fixture {
            let dir = tempfile::tempdir().unwrap();
            std::fs::write(dir.path().join("fileseek_fake.py"), FAKE_BACKEND_SCRIPT).unwrap();
            Fixture { dir }
        }
        fn connection_file(&self) -> PathBuf {
            self.dir.path().join("connection.json")
        }
        fn files(&self) -> SidecarFiles {
            SidecarFiles {
                log: self.dir.path().join("logs/backend.log"),
                pidfile: self.dir.path().join("backend.pid"),
            }
        }
        fn command(&self, extra: &[&str]) -> BackendCommand {
            let mut args = vec![
                self.dir
                    .path()
                    .join("fileseek_fake.py")
                    .to_string_lossy()
                    .into_owned(),
                self.connection_file().to_string_lossy().into_owned(),
            ];
            args.extend(extra.iter().map(|s| s.to_string()));
            BackendCommand {
                program: "python3".into(),
                args,
                env: Vec::new(),
                env_remove: Vec::new(),
            }
        }
    }

    #[cfg(unix)]
    fn alive(pid: i32) -> bool {
        // SAFETY: signal 0 only checks liveness.
        unsafe { libc::kill(pid, 0) == 0 }
    }

    #[test]
    fn start_reports_the_port_and_captures_output_in_the_log() {
        let fx = Fixture::new();
        let mut sidecar = Sidecar::start(
            &fx.command(&[]),
            &fx.connection_file(),
            &fx.files(),
            Duration::from_secs(15),
            &AtomicBool::new(false),
        )
        .unwrap();

        assert!(sidecar.port() > 0);
        assert!(sidecar.exited().is_none());
        assert!(sidecar.log_tail().contains("backend output"));
        sidecar.stop();
        assert!(!fx.files().pidfile.exists());
    }

    #[test]
    fn a_backend_that_exits_is_reported_with_its_output() {
        let fx = Fixture::new();
        let command = BackendCommand {
            program: "python3".into(),
            args: vec![
                "-c".into(),
                "import sys; print('boom: no module named torch'); sys.exit(3)".into(),
            ],
            env: Vec::new(),
            env_remove: Vec::new(),
        };

        let result = Sidecar::start(
            &command,
            &fx.connection_file(),
            &fx.files(),
            Duration::from_secs(10),
            &AtomicBool::new(false),
        );

        match result {
            Err(SidecarError::ExitedEarly { code, log_tail }) => {
                assert_eq!(code, Some(3));
                assert!(log_tail.contains("no module named torch"));
            }
            other => panic!("expected ExitedEarly, got {:?}", other.map(|s| s.port())),
        }
    }

    #[test]
    fn times_out_when_the_backend_never_becomes_ready() {
        let fx = Fixture::new();
        let command = BackendCommand {
            program: "python3".into(),
            args: vec!["-c".into(), "import time; time.sleep(60)".into()],
            env: Vec::new(),
            env_remove: Vec::new(),
        };

        let result = Sidecar::start(
            &command,
            &fx.connection_file(),
            &fx.files(),
            Duration::from_secs(1),
            &AtomicBool::new(false),
        );

        assert!(matches!(result, Err(SidecarError::Timeout { .. })));
    }

    #[cfg(unix)]
    #[test]
    fn stop_ends_the_backend_and_its_workers() {
        let fx = Fixture::new();
        let mut sidecar = Sidecar::start(
            &fx.command(&["spawn-worker"]),
            &fx.connection_file(),
            &fx.files(),
            Duration::from_secs(15),
            &AtomicBool::new(false),
        )
        .unwrap();
        let pgid = sidecar.child.id() as i32;

        sidecar.stop();

        let deadline = Instant::now() + Duration::from_secs(3);
        while group_alive(pgid) && Instant::now() < deadline {
            std::thread::sleep(POLL_INTERVAL);
        }
        assert!(
            !group_alive(pgid),
            "worker in group {pgid} should be gone too"
        );
    }

    #[test]
    fn a_shutdown_request_needs_this_runs_token() {
        let fx = Fixture::new();
        let mut sidecar = Sidecar::start(
            &fx.command(&[]),
            &fx.connection_file(),
            &fx.files(),
            Duration::from_secs(15),
            &AtomicBool::new(false),
        )
        .unwrap();
        assert_eq!(sidecar.token, "t");

        assert!(!request_shutdown(sidecar.port(), "wrong"));
        assert!(sidecar.exited().is_none());

        assert!(request_shutdown(sidecar.port(), &sidecar.token));
        let deadline = Instant::now() + Duration::from_secs(5);
        while sidecar.exited().is_none() && Instant::now() < deadline {
            std::thread::sleep(POLL_INTERVAL);
        }
        assert!(
            sidecar.exited().is_some(),
            "the backend ignored the shutdown request"
        );
        sidecar.stop();
    }

    #[cfg(unix)]
    #[test]
    fn stop_waits_for_a_backend_still_draining_its_queue() {
        let fx = Fixture::new();
        let drained = fx.dir.path().join("drained");
        // Longer than the old 5 s grace, well inside the backend's 10 s drain.
        let mut sidecar = Sidecar::start(
            &fx.command(&["slow-drain", &drained.to_string_lossy(), "7"]),
            &fx.connection_file(),
            &fx.files(),
            Duration::from_secs(15),
            &AtomicBool::new(false),
        )
        .unwrap();

        sidecar.stop();

        assert!(
            drained.exists(),
            "the backend was killed before it finished draining"
        );
    }

    #[cfg(unix)]
    #[test]
    fn a_backend_left_by_a_killed_app_is_stopped_on_the_next_start() {
        let fx = Fixture::new();
        let first = Sidecar::start(
            &fx.command(&[]),
            &fx.connection_file(),
            &fx.files(),
            Duration::from_secs(15),
            &AtomicBool::new(false),
        )
        .unwrap();
        let orphan = first.child.id() as i32;
        // What `tauri dev` does on a rebuild: the app goes away without running `stop`.
        std::mem::forget(first);
        assert!(alive(orphan));

        let mut second = Sidecar::start(
            &fx.command(&[]),
            &fx.connection_file(),
            &fx.files(),
            Duration::from_secs(15),
            &AtomicBool::new(false),
        )
        .unwrap();

        // `wait` was never called on the orphan, so it may linger as a zombie; the group
        // signal check treats zombies as gone only once reaped, so check the process state.
        let state = Command::new("ps")
            .args(["-o", "stat=", "-p", &orphan.to_string()])
            .output()
            .unwrap();
        let state = String::from_utf8_lossy(&state.stdout);
        assert!(
            state.trim().is_empty() || state.starts_with('Z'),
            "orphan still running: {state}"
        );
        second.stop();
    }

    #[cfg(unix)]
    #[test]
    fn a_reused_pid_in_the_pidfile_is_left_alone() {
        use std::os::unix::process::CommandExt;
        let fx = Fixture::new();
        let mut unrelated = Command::new("sleep")
            .arg("30")
            .process_group(0)
            .spawn()
            .unwrap();
        std::fs::write(&fx.files().pidfile, unrelated.id().to_string()).unwrap();

        stop_stale_backend(&fx.files().pidfile);

        assert!(
            matches!(unrelated.try_wait(), Ok(None)),
            "unrelated process was killed"
        );
        let _ = unrelated.kill();
        let _ = unrelated.wait();
    }

    #[test]
    fn production_command_isolates_the_interpreter() {
        let command = BackendCommand::production(
            Path::new("/data/runtime/rt-x/python/bin/python3"),
            Path::new("/app/Resources/backend"),
            Path::new("/data/models/m"),
        );

        assert_eq!(command.args, ["-m", "fileseek"]);
        assert!(command
            .env
            .contains(&("PYTHONPATH".into(), "/app/Resources/backend".into())));
        assert!(command
            .env
            .contains(&("EMBEDDING_MODEL_CACHE_DIR".into(), "/data/models/m".into())));
        assert!(command.env_remove.contains(&"PYTHONHOME".to_owned()));
    }

    #[test]
    fn repo_root_from_exe_walks_up_past_desktop_and_target() {
        let exe = Path::new("/repo/desktop/src-tauri/target/debug/desktop");
        assert_eq!(repo_root_from_exe(exe).unwrap(), Path::new("/repo"));
    }
}
