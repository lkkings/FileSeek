use std::io::Read;

use serde::Deserialize;
use tauri::http::{Request, Response};

const TOKEN_HEADER: &str = "X-FileSeek-Token";

#[derive(Clone, Deserialize)]
pub struct BackendConnection {
    pub port: u16,
    pub token: String,
}

#[derive(Clone, Default)]
pub struct PreviewTransportState {
    pub connection: Option<BackendConnection>,
}

pub fn connection_file_path() -> std::path::PathBuf {
    #[cfg(target_os = "windows")]
    {
        let base = dirs::config_dir().unwrap_or_else(|| std::path::PathBuf::from("."));
        base.join("FileSeek").join("connection.json")
    }

    #[cfg(target_os = "macos")]
    {
        let base = dirs::config_dir().unwrap_or_else(|| std::path::PathBuf::from("."));
        base.join("FileSeek").join("connection.json")
    }

    #[cfg(all(unix, not(target_os = "macos")))]
    {
        let base = dirs::config_dir().unwrap_or_else(|| std::path::PathBuf::from("."));
        base.join("fileseek").join("connection.json")
    }
}

pub fn load_connection(path: &std::path::Path) -> Option<BackendConnection> {
    let contents = std::fs::read_to_string(path).ok()?;
    let connection = serde_json::from_str::<BackendConnection>(&contents).ok()?;
    (!connection.token.is_empty()).then_some(connection)
}

pub fn is_approved_preview_request(method: &str, path_and_query: &str) -> bool {
    if method != "GET" && method != "HEAD" {
        return false;
    }

    let (path, query) = match path_and_query.split_once('?') {
        Some((path, query)) => (path, Some(query)),
        None => (path_and_query, None),
    };

    let segments: Vec<&str> = path.trim_matches('/').split('/').collect();
    if segments.len() != 6 || segments[..4] != ["api", "v1", "library", "files"] {
        return false;
    }

    let (file_id, action) = if segments[4] == "preview" {
        (segments[5], segments[4])
    } else {
        (segments[4], segments[5])
    };
    if file_id.is_empty() || file_id.contains("..") || action.contains("..") {
        return false;
    }

    let is_preview = action == "preview";
    let is_thumbnail = action == "thumbnail";
    if !is_preview && !is_thumbnail {
        return false;
    }

    match query {
        None => true,
        Some(query) => query == "size=list" || query == "size=detail",
    }
}

pub fn backend_url(connection: &BackendConnection, path_and_query: &str) -> String {
    format!("http://127.0.0.1:{}{}", connection.port, path_and_query)
}

pub fn handle_preview_request(
    state: &PreviewTransportState,
    request: &Request<Vec<u8>>,
) -> Response<Vec<u8>> {
    let path_and_query = request
        .uri()
        .path_and_query()
        .map(|value| value.as_str())
        .unwrap_or_else(|| request.uri().path());

    if !is_approved_preview_request(request.method().as_str(), path_and_query) {
        return error_response(403, "Preview path is not allowed");
    }

    let Some(connection) = state.connection.as_ref() else {
        return error_response(503, "Backend connection is unavailable");
    };

    let mut forwarded_request = ureq::get(&backend_url(connection, path_and_query));
    forwarded_request = forwarded_request.set(TOKEN_HEADER, connection.token.as_str());

    if let Some(range) = request.headers().get("range") {
        if let Ok(range) = range.to_str() {
            forwarded_request = forwarded_request.set("Range", range);
        }
    }

    match forwarded_request.call() {
        Ok(response) => {
            let status = response.status();
            let headers = response
                .headers_names()
                .into_iter()
                .filter(|name| SAFE_RESPONSE_HEADERS.contains(&name.as_str()))
                .filter_map(|name| response.header(&name).map(|value| (name, value.to_owned())))
                .collect::<Vec<_>>();
            let mut body = Vec::new();
            let mut reader = response.into_reader();
            if reader.read_to_end(&mut body).is_err() {
                return error_response(502, "Preview response could not be read");
            }

            response_from_parts(status, body, headers)
        }
        Err(_) => error_response(502, "Preview request failed"),
    }
}

fn response_from_parts(
    status: u16,
    body: Vec<u8>,
    headers: Vec<(String, String)>,
) -> Response<Vec<u8>> {
    let mut builder = Response::builder()
        .status(status)
        .header("Access-Control-Allow-Origin", "*");
    for (name, value) in headers {
        builder = builder.header(name, value);
    }
    builder
        .body(body)
        .unwrap_or_else(|_| error_response(500, "Preview response could not be constructed"))
}

const SAFE_RESPONSE_HEADERS: [&str; 9] = [
    "accept-ranges",
    "cache-control",
    "content-disposition",
    "content-length",
    "content-range",
    "content-type",
    "etag",
    "last-modified",
    "x-content-type-options",
];

fn error_response(status: u16, message: &str) -> Response<Vec<u8>> {
    Response::builder()
        .status(status)
        .header("Content-Type", "text/plain; charset=utf-8")
        .header("Access-Control-Allow-Origin", "*")
        .body(message.as_bytes().to_vec())
        .unwrap_or_else(|_| {
            Response::builder()
                .status(500)
                .body(Vec::new())
                .expect("static response")
        })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn allows_only_preview_and_thumbnail_get_requests() {
        assert!(is_approved_preview_request(
            "GET",
            "/api/v1/library/files/preview/file-1"
        ));
        assert!(is_approved_preview_request(
            "GET",
            "/api/v1/library/files/file-1/thumbnail?size=list"
        ));
        assert!(is_approved_preview_request(
            "HEAD",
            "/api/v1/library/files/file-1/thumbnail?size=detail"
        ));
    }

    #[test]
    fn rejects_disallowed_paths_queries_and_methods() {
        assert!(!is_approved_preview_request(
            "GET",
            "/api/v1/library/folders"
        ));
        assert!(!is_approved_preview_request(
            "GET",
            "/api/v1/library/files/file-1/content"
        ));
        assert!(!is_approved_preview_request(
            "GET",
            "/api/v1/library/files/file-1/thumbnail?size=huge"
        ));
        assert!(!is_approved_preview_request(
            "POST",
            "/api/v1/library/files/preview/file-1"
        ));
    }

    #[test]
    fn returns_service_unavailable_without_a_backend_connection() {
        let request = Request::get("/api/v1/library/files/preview/file-1")
            .body(Vec::new())
            .expect("request");
        let state = PreviewTransportState::default();

        let response = handle_preview_request(&state, &request);

        assert_eq!(response.status(), 503);
        assert_eq!(response.headers()["access-control-allow-origin"], "*");
    }

    #[test]
    fn preserves_binary_range_and_cache_headers() {
        let response = response_from_parts(
            206,
            b"partial-video".to_vec(),
            vec![
                ("content-type".to_owned(), "video/mp4".to_owned()),
                ("content-range".to_owned(), "bytes 6-10/27".to_owned()),
                ("accept-ranges".to_owned(), "bytes".to_owned()),
                ("content-length".to_owned(), "5".to_owned()),
                (
                    "cache-control".to_owned(),
                    "private, max-age=86400".to_owned(),
                ),
            ],
        );

        assert_eq!(response.status(), 206);
        assert_eq!(response.body(), b"partial-video");
        assert_eq!(response.headers()["content-type"], "video/mp4");
        assert_eq!(response.headers()["content-range"], "bytes 6-10/27");
        assert_eq!(response.headers()["accept-ranges"], "bytes");
        assert_eq!(response.headers()["access-control-allow-origin"], "*");
        assert_eq!(
            response.headers()["cache-control"],
            "private, max-age=86400"
        );
    }
}
