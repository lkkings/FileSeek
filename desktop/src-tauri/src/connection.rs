//! The single command the UI reaches the backend through, restored from before the
//! front-end rewrite (`d80407a:desktop/src-tauri/src/connection.rs`).
//!
//! The request is issued here, in Rust, rather than with `fetch` in the WebView. The
//! backend checks the request's origin, and a WebView's origin (`tauri://localhost`) is
//! never `http://127.0.0.1:<port>`, so a browser-side fetch is refused with 403 — and
//! would fail CORS preflight first, since the backend sends no CORS headers. A request
//! from Rust carries no `Origin` at all, which is the non-browser client the backend
//! allows. Keeping the token on this side also means it never reaches the WebView.
//!
//! The connection file is read on every call: the backend may restart on a new port
//! (after a crash, or once the runtime finishes installing), and a cached copy would go
//! on pointing at the old one.

use std::time::Duration;

use serde::Serialize;

use crate::preview_protocol::{connection_file_path, load_connection, BackendConnection};

const TOKEN_HEADER: &str = "X-FileSeek-Token";
const REQUEST_TIMEOUT: Duration = Duration::from_secs(30);

/// A backend response, passed back to the UI as-is.
///
/// The status travels with the body because the UI distinguishes cases by it, so a
/// non-2xx is a normal return here — only a request that got no answer is an error.
#[derive(Debug, Serialize)]
pub struct ApiResponse {
    pub status: u16,
    pub body: String,
}

/// Sends one request to the backend with the token attached.
pub fn perform_request(
    connection: &BackendConnection,
    method: &str,
    path: &str,
    body: Option<String>,
) -> Result<ApiResponse, String> {
    let url = format!("http://127.0.0.1:{}{}", connection.port, path);
    let request = ureq::request(method, &url)
        .set(TOKEN_HEADER, &connection.token)
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
        Err(ureq::Error::Status(status, response)) => Ok(ApiResponse {
            status,
            body: response.into_string().unwrap_or_default(),
        }),
        Err(error) => Err(format!("could not reach the FileSeek backend: {error}")),
    }
}

/// The backend's error envelope, with a code the UI turns into the activation screen.
fn license_required() -> ApiResponse {
    ApiResponse {
        status: 403,
        body: serde_json::json!({
            "status": "error",
            "data": null,
            "error": {"code": "LICENSE_REQUIRED", "message": "FileSeek requires activation"},
        })
        .to_string(),
    }
}

/// The UI's one way to call the backend.
///
/// Runs on Tauri's async pool (`async`) so a slow backend call does not hold up the
/// main thread.
#[tauri::command]
pub async fn api_request(
    method: String,
    path: String,
    body: Option<String>,
    license: tauri::State<'_, crate::license::SharedLicense>,
) -> Result<ApiResponse, String> {
    // Without a license the backend is stopped and the UI shows only the activation
    // screen; this covers the moments between losing the license and the backend exiting.
    if !license.entitlement().is_licensed() {
        return Ok(license_required());
    }
    let connection = load_connection(&connection_file_path())
        .ok_or_else(|| "the FileSeek backend is not running".to_owned())?;
    tauri::async_runtime::spawn_blocking(move || perform_request(&connection, &method, &path, body))
        .await
        .map_err(|error| error.to_string())?
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::{BufRead, BufReader, Read, Write};
    use std::net::TcpListener;

    /// Answers one request with the token it saw and the body it got, or 401 when the
    /// token is wrong — the contract `bootstrap/auth.py` enforces.
    fn one_shot_backend(expected_token: &'static str) -> u16 {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let port = listener.local_addr().unwrap().port();
        std::thread::spawn(move || {
            let (stream, _) = listener.accept().unwrap();
            let mut reader = BufReader::new(stream.try_clone().unwrap());
            let mut request_line = String::new();
            reader.read_line(&mut request_line).unwrap();
            let (mut token, mut length) = (String::new(), 0usize);
            loop {
                let mut line = String::new();
                reader.read_line(&mut line).unwrap();
                if line == "\r\n" {
                    break;
                }
                let lower = line.to_ascii_lowercase();
                if let Some(value) = lower.strip_prefix("x-fileseek-token:") {
                    token = value.trim().to_owned();
                }
                if let Some(value) = lower.strip_prefix("content-length:") {
                    length = value.trim().parse().unwrap();
                }
            }
            let mut body = vec![0; length];
            reader.read_exact(&mut body).unwrap();
            let (status, payload) = if token == expected_token {
                (
                    "200 OK",
                    format!("{} {}", request_line.trim(), String::from_utf8_lossy(&body)),
                )
            } else {
                ("401 Unauthorized", "authentication required".to_owned())
            };
            let mut stream = stream;
            write!(
                stream,
                "HTTP/1.1 {status}\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{payload}",
                payload.len()
            )
            .unwrap();
        });
        port
    }

    #[test]
    fn an_authenticated_request_reaches_the_backend() {
        let port = one_shot_backend("secret");
        let connection = BackendConnection {
            port,
            token: "secret".into(),
        };

        let response = perform_request(
            &connection,
            "POST",
            "/api/v1/tasks",
            Some("{\"a\":1}".into()),
        )
        .unwrap();

        assert_eq!(response.status, 200);
        assert_eq!(response.body, "POST /api/v1/tasks HTTP/1.1 {\"a\":1}");
    }

    #[test]
    fn a_non_2xx_answer_is_returned_not_raised() {
        let port = one_shot_backend("secret");
        let connection = BackendConnection {
            port,
            token: "stale".into(),
        };

        let response = perform_request(&connection, "GET", "/api/v1/tasks", None).unwrap();

        assert_eq!(response.status, 401);
    }

    #[test]
    fn the_refusal_uses_the_backends_error_envelope() {
        let response = license_required();
        let body: serde_json::Value = serde_json::from_str(&response.body).unwrap();
        assert_eq!(response.status, 403);
        assert_eq!(body["error"]["code"], "LICENSE_REQUIRED");
    }

    #[test]
    fn no_answer_is_an_error() {
        let connection = BackendConnection {
            port: 9,
            token: "t".into(),
        };

        assert!(perform_request(&connection, "GET", "/health", None).is_err());
    }
}
