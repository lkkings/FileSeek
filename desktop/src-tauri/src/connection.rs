//! Reading the connection file, and the single command the UI reaches the backend through.
//!
//! The backend publishes `{port, token}` to a file in the user's config directory (see
//! `fileseek.api.connection` on the Python side) and requires that token on every request
//! but `/health`.
//!
//! The request is issued here, in Rust, rather than with `fetch` in the WebView. The
//! backend also checks the request's origin, and a WebView's origin (`tauri://localhost`,
//! or `http://localhost:1420` in dev) is never equal to `http://127.0.0.1:<port>`, so a
//! browser-side fetch is refused with 403 — and would fail CORS preflight first, since the
//! backend sends no CORS headers. A request from Rust carries no `Origin` or
//! `Sec-Fetch-Site` at all, which is the non-browser client the backend allows.
//!
//! Keeping the token on this side also means it never has to be handed to the WebView.

use std::io::Read;
use std::path::{Path, PathBuf};
use std::time::Duration;

use serde::{Deserialize, Serialize};

/// The header the backend expects the token in (`fileseek.api.auth.TOKEN_HEADER`).
const TOKEN_HEADER: &str = "X-FileSeek-Token";

/// How long a single backend request may take before it is reported as failed.
const REQUEST_TIMEOUT: Duration = Duration::from_secs(30);

/// Where the backend listens, and the token needed to talk to it.
#[derive(Debug, Clone, Deserialize)]
pub struct ConnectionInfo {
    pub port: u16,
    pub token: String,
}

/// Why the connection file could not be used.
#[derive(Debug)]
pub enum ConnectionError {
    /// No connection file, so the backend has not published one yet.
    Missing(PathBuf),
    /// The file exists but is not the `{port, token}` shape.
    Malformed(String),
}

impl std::fmt::Display for ConnectionError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ConnectionError::Missing(path) => write!(
                f,
                "no connection file at {}: the FileSeek backend may not be running",
                path.display()
            ),
            ConnectionError::Malformed(detail) => {
                write!(f, "the connection file could not be read: {detail}")
            }
        }
    }
}

impl std::error::Error for ConnectionError {}

impl ConnectionInfo {
    pub fn base_url(&self) -> String {
        format!("http://127.0.0.1:{}", self.port)
    }

    /// Read the connection info the running backend published.
    pub fn read(path: &Path) -> Result<ConnectionInfo, ConnectionError> {
        if !path.is_file() {
            return Err(ConnectionError::Missing(path.to_path_buf()));
        }
        let contents = std::fs::read_to_string(path)
            .map_err(|error| ConnectionError::Malformed(error.to_string()))?;
        let info: ConnectionInfo = serde_json::from_str(&contents)
            .map_err(|error| ConnectionError::Malformed(error.to_string()))?;
        if info.token.is_empty() {
            return Err(ConnectionError::Malformed("the token is empty".to_string()));
        }
        Ok(info)
    }
}

/// A backend response, passed back to the UI as-is.
///
/// The status travels with the body because the UI distinguishes cases by it: 401 means
/// the token is stale, 503 that search has no weights yet. So a non-2xx is a normal
/// return here, not an error — only a request that never got an answer is an error.
#[derive(Debug, Serialize)]
pub struct ApiResponse {
    pub status: u16,
    pub body: String,
}

/// Send one request to the backend with the token attached.
///
/// Split out from the Tauri command so it can be tested without a Tauri runtime.
pub fn perform_request(
    info: &ConnectionInfo,
    method: &str,
    path: &str,
    body: Option<String>,
) -> Result<ApiResponse, String> {
    let url = format!("{}{}", info.base_url(), path);
    let request = ureq::request(method, &url)
        .set(TOKEN_HEADER, &info.token)
        .timeout(REQUEST_TIMEOUT);

    let outcome = match body {
        Some(payload) => request
            .set("Content-Type", "application/json")
            .send_string(&payload),
        None => request.call(),
    };

    match outcome {
        Ok(response) => Ok(ApiResponse {
            status: response.status(),
            body: response.into_string().unwrap_or_default(),
        }),
        // The backend answered, just not with a 2xx. The UI needs to see it.
        Err(ureq::Error::Status(status, response)) => Ok(ApiResponse {
            status,
            body: response.into_string().unwrap_or_default(),
        }),
        // Nothing answered: the backend is down, or the port moved.
        Err(error) => Err(format!("could not reach the FileSeek backend: {error}")),
    }
}

/// A backend response whose body is bytes rather than text.
///
/// Separate from `ApiResponse` because that one carries a `String`: an image or a chunk of
/// video is not valid UTF-8, and `into_string` would mangle it. Used by the media protocol
/// (`media.rs`), which hands these bytes to the WebView.
#[derive(Debug)]
pub struct BinaryResponse {
    pub status: u16,
    pub body: Vec<u8>,
    pub content_type: String,
    /// `Content-Range`, present when the backend answered a Range request with a 206.
    pub content_range: Option<String>,
}

/// Send one request and read its body as bytes, optionally with extra headers.
///
/// `extra_headers` carries the `Range` a video player asks for, so seeking pulls only the
/// bytes it needs rather than the whole file.
pub fn perform_binary_request(
    info: &ConnectionInfo,
    method: &str,
    path: &str,
    extra_headers: &[(String, String)],
) -> Result<BinaryResponse, String> {
    let url = format!("{}{}", info.base_url(), path);
    let mut request = ureq::request(method, &url)
        .set(TOKEN_HEADER, &info.token)
        .timeout(REQUEST_TIMEOUT);
    for (name, value) in extra_headers {
        request = request.set(name, value);
    }

    let (status, response) = match request.call() {
        Ok(response) => (response.status(), response),
        // The backend answered, just not with a 2xx — a 404 for a file no longer in the
        // library, say. The status has to reach the WebView so the UI can say which it was.
        Err(ureq::Error::Status(status, response)) => (status, response),
        Err(error) => return Err(format!("could not reach the FileSeek backend: {error}")),
    };

    let content_type = response
        .header("Content-Type")
        .unwrap_or("application/octet-stream")
        .to_string();
    let content_range = response.header("Content-Range").map(str::to_string);

    let mut body = Vec::new();
    response
        .into_reader()
        .read_to_end(&mut body)
        .map_err(|error| format!("could not read the response body: {error}"))?;

    Ok(BinaryResponse { status, body, content_type, content_range })
}

/// The connection file path for the current user, resolved from their home directory.
pub fn default_connection_file() -> Result<PathBuf, String> {
    let home = home_dir().ok_or_else(|| "could not determine the home directory".to_string())?;
    Ok(crate::sidecar::connection_file_path(&home))
}

pub fn home_dir() -> Option<PathBuf> {
    #[cfg(target_os = "windows")]
    {
        std::env::var_os("USERPROFILE").map(PathBuf::from)
    }
    #[cfg(not(target_os = "windows"))]
    {
        std::env::var_os("HOME").map(PathBuf::from)
    }
}

/// The UI's one way to call the backend: reads the published token, attaches it, returns
/// whatever came back.
#[tauri::command]
pub fn api_request(
    method: String,
    path: String,
    body: Option<String>,
) -> Result<ApiResponse, String> {
    let connection_file = default_connection_file()?;
    let info = ConnectionInfo::read(&connection_file).map_err(|error| error.to_string())?;
    perform_request(&info, &method, &path, body)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;
    use std::process::{Child, Command, Stdio};
    use std::time::Instant;

    /// A stand-in for the backend that enforces the same token contract as
    /// `fileseek.api.auth.TokenAuthMiddleware`: the token header must match or the
    /// request is refused with 401. On success it echoes back what it saw, so a test
    /// can assert the token actually travelled.
    ///
    /// The server is bound before the connection file is written, so a file on disk
    /// means the port is already accepting connections.
    const FAKE_BACKEND_SCRIPT: &str = r#"
import http.server, json, socket, sys, threading, time

connection_file, expected = sys.argv[1], sys.argv[2]

def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]

class Handler(http.server.BaseHTTPRequestHandler):
    def respond(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def handle_any(self):
        if self.headers.get("X-FileSeek-Token") != expected:
            self.respond(401, {"status": "error", "data": None, "error": "authentication required"})
            return
        length = int(self.headers.get("Content-Length") or 0)
        sent = self.rfile.read(length).decode() if length else None
        self.respond(200, {
            "status": "success",
            "data": {"method": self.command, "path": self.path, "body": sent},
            "error": None,
        })

    do_GET = handle_any
    do_POST = handle_any

    def log_message(self, *args):
        pass

server = http.server.HTTPServer(("127.0.0.1", free_port()), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()

with open(connection_file, "w") as f:
    json.dump({"port": server.server_address[1], "token": expected}, f)

while True:
    time.sleep(1)
"#;

    const TEST_TOKEN: &str = "0123456789abcdef0123456789abcdef";

    /// Owns the fake backend process and its temp directory so neither outlives the test.
    struct FakeBackend {
        child: Child,
        dir: PathBuf,
        connection_file: PathBuf,
    }

    impl Drop for FakeBackend {
        fn drop(&mut self) {
            let _ = self.child.kill();
            let _ = self.child.wait();
            std::fs::remove_dir_all(&self.dir).ok();
        }
    }

    fn temp_dir(name: &str) -> PathBuf {
        let dir = std::env::temp_dir().join(format!(
            "fileseek-connection-{}-{name}",
            std::process::id()
        ));
        std::fs::remove_dir_all(&dir).ok();
        std::fs::create_dir_all(&dir).unwrap();
        dir
    }

    fn start_fake_backend(name: &str) -> FakeBackend {
        let dir = temp_dir(name);
        let script = dir.join("fake_backend.py");
        std::fs::File::create(&script)
            .unwrap()
            .write_all(FAKE_BACKEND_SCRIPT.as_bytes())
            .unwrap();
        let connection_file = dir.join("connection.json");

        let child = Command::new("python3")
            .arg(&script)
            .arg(&connection_file)
            .arg(TEST_TOKEN)
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .expect("python3 should be available to run the fake backend");

        let backend = FakeBackend { child, dir, connection_file };

        let deadline = Instant::now() + Duration::from_secs(15);
        while !backend.connection_file.is_file() {
            assert!(
                Instant::now() < deadline,
                "the fake backend never published a connection file"
            );
            std::thread::sleep(Duration::from_millis(50));
        }
        backend
    }

    fn write_connection_file(dir: &Path, contents: &str) -> PathBuf {
        let path = dir.join("connection.json");
        std::fs::File::create(&path)
            .unwrap()
            .write_all(contents.as_bytes())
            .unwrap();
        path
    }

    #[test]
    fn read_returns_the_published_port_and_token() {
        let dir = temp_dir("read-ok");
        let path = write_connection_file(&dir, r#"{"port": 51234, "token": "abc123"}"#);

        let info = ConnectionInfo::read(&path).unwrap();

        assert_eq!(info.port, 51234);
        assert_eq!(info.token, "abc123");
        assert_eq!(info.base_url(), "http://127.0.0.1:51234");
        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn read_reports_a_missing_connection_file() {
        let dir = temp_dir("read-missing");

        let result = ConnectionInfo::read(&dir.join("connection.json"));

        assert!(matches!(result, Err(ConnectionError::Missing(_))));
        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn read_rejects_a_malformed_connection_file() {
        let dir = temp_dir("read-malformed");
        let path = write_connection_file(&dir, "not json at all");

        let result = ConnectionInfo::read(&path);

        assert!(matches!(result, Err(ConnectionError::Malformed(_))));
        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn read_rejects_an_empty_token() {
        let dir = temp_dir("read-empty-token");
        let path = write_connection_file(&dir, r#"{"port": 51234, "token": ""}"#);

        let result = ConnectionInfo::read(&path);

        assert!(matches!(result, Err(ConnectionError::Malformed(_))));
        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn an_authenticated_request_reaches_the_backend() {
        let backend = start_fake_backend("auth-ok");
        let info = ConnectionInfo::read(&backend.connection_file).unwrap();

        let response = perform_request(&info, "GET", "/tasks", None).unwrap();

        assert_eq!(response.status, 200, "body: {}", response.body);
        let parsed: serde_json::Value = serde_json::from_str(&response.body).unwrap();
        assert_eq!(parsed["status"], "success");
        assert_eq!(parsed["data"]["path"], "/tasks");
        assert_eq!(parsed["data"]["method"], "GET");
    }

    #[test]
    fn a_request_with_the_wrong_token_is_refused() {
        // Proves the fake backend really enforces the token, so the test above is
        // evidence the token travelled rather than that nothing was checked.
        let backend = start_fake_backend("auth-wrong");
        let mut info = ConnectionInfo::read(&backend.connection_file).unwrap();
        info.token = "wrong-token".to_string();

        let response = perform_request(&info, "GET", "/tasks", None).unwrap();

        assert_eq!(response.status, 401);
    }

    #[test]
    fn a_post_body_is_sent_through() {
        let backend = start_fake_backend("post-body");
        let info = ConnectionInfo::read(&backend.connection_file).unwrap();
        let payload = r#"{"paths": ["/tmp/a.png"]}"#;

        let response =
            perform_request(&info, "POST", "/ingest", Some(payload.to_string())).unwrap();

        assert_eq!(response.status, 200, "body: {}", response.body);
        let parsed: serde_json::Value = serde_json::from_str(&response.body).unwrap();
        assert_eq!(parsed["data"]["body"], payload);
    }

    #[test]
    fn an_unreachable_backend_is_an_error_not_a_status() {
        // Port 1 is never a FileSeek backend, so nothing answers.
        let info = ConnectionInfo { port: 1, token: TEST_TOKEN.to_string() };

        let result = perform_request(&info, "GET", "/tasks", None);

        assert!(result.is_err());
    }
}
