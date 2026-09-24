//! Helpers for tests that need a real backend process to act on.
//!
//! The lifecycle tests are about whether a process survives a window close and dies on
//! quit, so they need something actually running rather than a stand-in object. This runs
//! a stdlib-only Python server that publishes a connection file and answers `/health`,
//! the same contract `Sidecar::start` waits on.

#![cfg(test)]

use std::io::Write;
use std::path::{Path, PathBuf};
use std::process::Child;
use std::time::Duration;

use crate::sidecar::{BackendCommand, Sidecar};

/// Publishes `{port, token}` then answers `/health`, and otherwise stays alive.
const FAKE_BACKEND_SCRIPT: &str = r#"
import http.server, json, socket, sys, threading, time

def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]

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

server = http.server.HTTPServer(("127.0.0.1", free_port()), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()

with open(sys.argv[1], "w") as f:
    json.dump({"port": server.server_address[1], "token": "test-token"}, f)

while True:
    time.sleep(1)
"#;

/// A temp directory that removes itself when the test ends.
pub struct TempDir {
    pub path: PathBuf,
}

impl Drop for TempDir {
    fn drop(&mut self) {
        std::fs::remove_dir_all(&self.path).ok();
    }
}

pub fn temp_dir(name: &str) -> TempDir {
    let path = std::env::temp_dir().join(format!("fileseek-{name}-{}", std::process::id()));
    std::fs::remove_dir_all(&path).ok();
    std::fs::create_dir_all(&path).unwrap();
    TempDir { path }
}

/// Start a backend stand-in and wait until it reports itself ready.
///
/// Returns the sidecar alongside the temp directory, which the caller holds for the
/// lifetime of the test so the script and connection file are not removed under it.
pub fn start_fake_sidecar(name: &str) -> (Sidecar, TempDir) {
    let dir = temp_dir(name);
    let script = dir.path.join("fake_backend.py");
    std::fs::File::create(&script)
        .unwrap()
        .write_all(FAKE_BACKEND_SCRIPT.as_bytes())
        .unwrap();
    let connection_file = dir.path.join("connection.json");

    let command = BackendCommand {
        program: "python3".to_string(),
        args: vec![
            script.to_string_lossy().into_owned(),
            connection_file.to_string_lossy().into_owned(),
        ],
    };

    let sidecar = Sidecar::start(&command, &connection_file, Duration::from_secs(20))
        .expect("the fake backend should become ready");
    (sidecar, dir)
}

/// Whether a pid is still running.
///
/// `kill(pid, 0)` sends no signal; it only reports whether the process can be signalled.
#[cfg(unix)]
pub fn is_alive(pid: u32) -> bool {
    // SAFETY: signal 0 performs the permission/existence check without delivering it.
    unsafe { libc::kill(pid as libc::pid_t, 0) == 0 }
}

/// Reap a child so a killed process does not linger as a zombie and read as alive.
#[allow(dead_code)]
pub fn reap(child: &mut Child) {
    let _ = child.wait();
}

/// The path a `Sidecar`'s fake backend published to, for assertions about it.
#[allow(dead_code)]
pub fn connection_file_in(dir: &Path) -> PathBuf {
    dir.join("connection.json")
}
