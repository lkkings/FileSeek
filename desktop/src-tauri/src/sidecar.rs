//! Starts and stops the Python backend as a child process.
//!
//! The backend picks its own port and publishes it, alongside an auth token, to a
//! connection file in the user's config directory (see `fileseek.api.connection` on the
//! Python side). This module spawns the backend, waits for that file to be rewritten and
//! for `/health` to answer, and stops the process on shutdown.
//!
//! Kept independent of any Tauri runtime so it can be exercised with `cargo test` alone.

use std::fmt;
use std::io::Read;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::time::{Duration, Instant};

/// How often the connection file and the health endpoint are polled while waiting
/// for the backend to come up.
const POLL_INTERVAL: Duration = Duration::from_millis(200);

/// How long `stop` waits for a graceful exit before killing the process outright.
const STOP_GRACE_PERIOD: Duration = Duration::from_secs(5);

/// A command to spawn the backend with: a program and its arguments.
#[derive(Debug, Clone)]
pub struct BackendCommand {
    pub program: String,
    pub args: Vec<String>,
}

impl BackendCommand {
    /// The command to run, resolved from `FILESEEK_BACKEND` when set (split on
    /// whitespace into program + args — used by tests and dev overrides), falling
    /// back to running the backend from the repo checkout via `uv`.
    pub fn resolve(repo_root: &Path) -> Self {
        if let Ok(raw) = std::env::var("FILESEEK_BACKEND") {
            let mut parts = raw.split_whitespace();
            let program = parts.next().unwrap_or_default().to_string();
            let args = parts.map(str::to_string).collect();
            return BackendCommand { program, args };
        }

        let backend_dir = repo_root.join("backend");
        BackendCommand {
            program: "uv".to_string(),
            args: vec![
                "run".to_string(),
                "--directory".to_string(),
                backend_dir.to_string_lossy().into_owned(),
                "python".to_string(),
                "-m".to_string(),
                "fileseek".to_string(),
            ],
        }
    }
}

/// Why the backend could not be started.
#[derive(Debug)]
pub enum SidecarError {
    /// The process itself could not be spawned (bad program name, permissions, ...).
    Spawn(std::io::Error),
    /// The process exited before it became ready.
    ExitedEarly { code: Option<i32>, stderr_tail: String },
    /// Neither the connection file nor `/health` were ready within the timeout.
    Timeout { stderr_tail: String },
}

impl fmt::Display for SidecarError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            SidecarError::Spawn(error) => write!(f, "could not start the backend: {error}"),
            SidecarError::ExitedEarly { code, stderr_tail } => write!(
                f,
                "the backend exited before it was ready (code {:?}): {stderr_tail}",
                code
            ),
            SidecarError::Timeout { stderr_tail } => write!(
                f,
                "the backend did not become ready in time: {stderr_tail}"
            ),
        }
    }
}

impl std::error::Error for SidecarError {}

/// A running backend process, plus the port it published.
pub struct Sidecar {
    child: Child,
    port: u16,
}

impl Sidecar {
    pub fn port(&self) -> u16 {
        self.port
    }

    /// The backend process's pid, so a caller can check whether it is still alive.
    pub fn pid(&self) -> u32 {
        self.child.id()
    }

    /// Start the backend and wait until it reports itself healthy.
    ///
    /// `connection_file` is the path the backend publishes `{port, token}` to. Its
    /// mtime is snapshotted before spawning so a stale file from a previous run is
    /// never mistaken for this one's.
    pub fn start(
        command: &BackendCommand,
        connection_file: &Path,
        timeout: Duration,
    ) -> Result<Sidecar, SidecarError> {
        let previous_mtime = file_mtime(connection_file);
        let deadline = Instant::now() + timeout;

        let mut child = Command::new(&command.program)
            .args(&command.args)
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .map_err(SidecarError::Spawn)?;

        let port = loop {
            if let Some(status) = child.try_wait().ok().flatten() {
                return Err(SidecarError::ExitedEarly {
                    code: status.code(),
                    stderr_tail: read_stderr_tail(&mut child),
                });
            }

            if file_mtime(connection_file) > previous_mtime {
                if let Some(port) = read_published_port(connection_file) {
                    break port;
                }
            }

            if Instant::now() >= deadline {
                return Err(SidecarError::Timeout {
                    stderr_tail: kill_and_read_stderr_tail(&mut child),
                });
            }

            std::thread::sleep(POLL_INTERVAL);
        };

        while !health_check_ok(port) {
            if let Some(status) = child.try_wait().ok().flatten() {
                return Err(SidecarError::ExitedEarly {
                    code: status.code(),
                    stderr_tail: read_stderr_tail(&mut child),
                });
            }
            if Instant::now() >= deadline {
                return Err(SidecarError::Timeout {
                    stderr_tail: kill_and_read_stderr_tail(&mut child),
                });
            }
            std::thread::sleep(POLL_INTERVAL);
        }

        Ok(Sidecar { child, port })
    }

    /// Stop the backend: a graceful signal first, so it drains its task queue and
    /// saves its indexes, then a forced kill if it does not exit in time.
    pub fn stop(&mut self) {
        terminate_gracefully(&mut self.child);

        let deadline = Instant::now() + STOP_GRACE_PERIOD;
        while Instant::now() < deadline {
            if matches!(self.child.try_wait(), Ok(Some(_))) {
                return;
            }
            std::thread::sleep(POLL_INTERVAL);
        }

        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}

impl Drop for Sidecar {
    fn drop(&mut self) {
        if matches!(self.child.try_wait(), Ok(None)) {
            self.stop();
        }
    }
}

fn file_mtime(path: &Path) -> Option<std::time::SystemTime> {
    std::fs::metadata(path).and_then(|meta| meta.modified()).ok()
}

/// The port from the connection file, or `None` while it is absent or half-written.
///
/// Delegates to `ConnectionInfo::read` so the file is parsed the same way here and in
/// the request path — including its rejection of an empty token, which is what keeps a
/// partially written file from being read as ready.
fn read_published_port(connection_file: &Path) -> Option<u16> {
    crate::connection::ConnectionInfo::read(connection_file)
        .ok()
        .map(|info| info.port)
}

fn health_check_ok(port: u16) -> bool {
    let url = format!("http://127.0.0.1:{port}/health");
    let response = match ureq::get(&url).timeout(Duration::from_secs(1)).call() {
        Ok(response) => response,
        Err(_) => return false,
    };
    if response.status() != 200 {
        return false;
    }
    let body: serde_json::Value = match response.into_json() {
        Ok(body) => body,
        Err(_) => return false,
    };
    body.get("data")
        .and_then(|data| data.get("status"))
        .and_then(|status| status.as_str())
        == Some("ok")
}

/// Kill the child, then read the stderr it left behind.
///
/// The order matters: `read_stderr_tail` reads to EOF, and a pipe reaches EOF only
/// once its writer is gone. Reading first from a child that is hung — exactly the
/// case a timeout describes — blocks forever instead of reporting the timeout.
fn kill_and_read_stderr_tail(child: &mut Child) -> String {
    let _ = child.kill();
    let _ = child.wait();
    read_stderr_tail(child)
}

/// The last portion of the child's stderr, for a readable failure message.
///
/// Reads to EOF, so the child must have exited; see `kill_and_read_stderr_tail`.
fn read_stderr_tail(child: &mut Child) -> String {
    const MAX_BYTES: usize = 4096;
    let Some(stderr) = child.stderr.as_mut() else {
        return String::new();
    };
    let mut buffer = Vec::new();
    let _ = stderr.read_to_end(&mut buffer);
    let start = buffer.len().saturating_sub(MAX_BYTES);
    String::from_utf8_lossy(&buffer[start..]).into_owned()
}

#[cfg(unix)]
fn terminate_gracefully(child: &mut Child) {
    // SAFETY: `kill` with a pid we own and a valid signal number is always safe to call.
    unsafe {
        libc::kill(child.id() as libc::pid_t, libc::SIGTERM);
    }
}

#[cfg(not(unix))]
fn terminate_gracefully(child: &mut Child) {
    // No SIGTERM equivalent on Windows; the backend's own signal handling for a
    // graceful uvicorn shutdown does not apply there either, so this is a plain kill.
    let _ = child.kill();
}

/// Resolves the repo root from the compiled binary's location, for the dev default.
///
/// `<repo>/desktop/src-tauri/target/debug/desktop` (or `.../release/desktop`): four
/// `parent()` calls from the exe reach `desktop/`, a fifth reaches the repo root.
/// `ancestors().nth(5)` applies `parent()` five times (`nth(0)` is the exe itself).
pub fn repo_root_from_exe(exe_path: &Path) -> Option<PathBuf> {
    exe_path
        .ancestors()
        .nth(5)
        .map(std::path::Path::to_path_buf)
}

/// The connection file path the backend publishes to, mirroring
/// `fileseek.paths.AppPaths.resolve().connection_file` on the Python side.
///
/// Must match exactly: this is the file `Sidecar::start` polls for the port the
/// backend just bound. `home` is injectable so a test does not depend on the
/// invoking user's real home directory.
pub fn connection_file_path(home: &Path) -> PathBuf {
    #[cfg(target_os = "windows")]
    {
        let roaming = std::env::var_os("APPDATA")
            .map(PathBuf::from)
            .unwrap_or_else(|| home.join("AppData").join("Roaming"));
        roaming.join("FileSeek").join("connection.json")
    }

    #[cfg(target_os = "macos")]
    {
        home.join("Library")
            .join("Application Support")
            .join("FileSeek")
            .join("connection.json")
    }

    #[cfg(all(unix, not(target_os = "macos")))]
    {
        let config_home = std::env::var_os("XDG_CONFIG_HOME")
            .map(PathBuf::from)
            .unwrap_or_else(|| home.join(".config"));
        config_home.join("fileseek").join("connection.json")
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;

    /// A tiny stdlib-only HTTP server, driven from a Python one-liner, that writes a
    /// connection file then answers `/health`. Runs against the system `python3`
    /// rather than the real backend, so these tests stay fast and dependency-free.
    const FAKE_BACKEND_SCRIPT: &str = r#"
import http.server, json, socket, sys, threading, time

def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]

port = free_port()

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            body = json.dumps({"data": {"status": "ok"}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args):
        pass

with open(sys.argv[1], "w") as f:
    json.dump({"port": port, "token": "test-token"}, f)

server = http.server.HTTPServer(("127.0.0.1", port), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
while True:
    time.sleep(1)
"#;

    const NEVER_READY_SCRIPT: &str = r#"
import time
while True:
    time.sleep(1)
"#;

    fn write_script(dir: &Path, name: &str, contents: &str) -> PathBuf {
        let path = dir.join(name);
        let mut file = std::fs::File::create(&path).unwrap();
        file.write_all(contents.as_bytes()).unwrap();
        path
    }

    fn python_command(script: &Path, extra_args: &[&str]) -> BackendCommand {
        let mut args = vec![script.to_string_lossy().into_owned()];
        args.extend(extra_args.iter().map(|s| s.to_string()));
        BackendCommand { program: "python3".to_string(), args }
    }

    #[test]
    fn start_reports_the_published_port_and_stays_alive() {
        let dir = std::env::temp_dir().join(format!("fileseek-sidecar-test-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let script = write_script(&dir, "fake_backend_ok.py", FAKE_BACKEND_SCRIPT);
        let connection_file = dir.join("connection.json");

        let command = python_command(&script, &[connection_file.to_string_lossy().as_ref()]);
        let mut sidecar =
            Sidecar::start(&command, &connection_file, Duration::from_secs(15)).unwrap();

        assert!(sidecar.port() > 0);
        assert!(matches!(sidecar.child.try_wait(), Ok(None)));

        sidecar.stop();
        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn start_times_out_when_the_backend_never_becomes_ready() {
        let dir = std::env::temp_dir().join(format!("fileseek-sidecar-test-{}", std::process::id() + 1));
        std::fs::create_dir_all(&dir).unwrap();
        let script = write_script(&dir, "never_ready.py", NEVER_READY_SCRIPT);
        let connection_file = dir.join("connection.json");

        let command = python_command(&script, &[]);
        let result = Sidecar::start(&command, &connection_file, Duration::from_secs(2));

        assert!(matches!(result, Err(SidecarError::Timeout { .. })));
        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn stop_ends_the_child_process() {
        let dir = std::env::temp_dir().join(format!("fileseek-sidecar-test-{}", std::process::id() + 2));
        std::fs::create_dir_all(&dir).unwrap();
        let script = write_script(&dir, "fake_backend_stop.py", FAKE_BACKEND_SCRIPT);
        let connection_file = dir.join("connection.json");

        let command = python_command(&script, &[connection_file.to_string_lossy().as_ref()]);
        let mut sidecar =
            Sidecar::start(&command, &connection_file, Duration::from_secs(15)).unwrap();
        let pid = sidecar.child.id();

        sidecar.stop();

        // SAFETY: `kill(pid, 0)` only checks liveness; it sends no signal.
        let alive = unsafe { libc::kill(pid as libc::pid_t, 0) } == 0;
        assert!(!alive, "process {pid} should have exited");

        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn repo_root_from_exe_walks_up_past_desktop_and_target() {
        let exe = Path::new("/repo/desktop/src-tauri/target/debug/desktop");

        let root = repo_root_from_exe(exe).unwrap();

        assert_eq!(root, Path::new("/repo"));
    }

    #[test]
    fn connection_file_path_ends_with_connection_json() {
        let home = Path::new("/home/testuser");

        let path = connection_file_path(home);

        assert_eq!(path.file_name().unwrap(), "connection.json");
        assert!(path.starts_with(home) || path.to_string_lossy().contains("FileSeek") || path.to_string_lossy().contains("fileseek"));
    }
}
