//! The `fileseek://` protocol: how image and video bytes reach the WebView.
//!
//! The backend requires its token in the `X-FileSeek-Token` header on every request, and
//! `<img src>` / `<video src>` cannot set a header. Nor can the token be handed to the
//! WebView — keeping it on the Rust side is the point of `connection.rs`. And it cannot go
//! in a query string, because the backend accepts it in the header only (deliberately: a
//! token in a URL lands in logs and history).
//!
//! So the WebView asks for `fileseek://localhost/media/<file_id>`, and this module answers:
//! it maps that to the backend's preview route, attaches the token, and hands back the bytes.
//! `Range` is forwarded in both directions, which is what lets a player seek to a segment
//! instead of downloading a whole video first (`design.md` §13).
//!
//! Two things keep this from becoming a general-purpose proxy into the backend:
//!
//! 1. Only `/media/<id>` is mapped. Any other path is refused here, before a request is
//!    made.
//! 2. Path segments are rejected if they contain a separator or are a `.`/`..` traversal.
//!
//! The mapping is a plain function, tested below without a WebView or a running backend.

use crate::connection::{
    default_connection_file, perform_binary_request, BinaryResponse, ConnectionInfo,
};

/// The scheme the WebView requests. Registered in `lib.rs`.
pub const SCHEME: &str = "fileseek";

/// What a `fileseek://` request maps to on the backend.
///
/// `None` for anything that is not the media endpoint — the refusal that keeps this from
/// proxying arbitrary paths.
pub fn backend_path_for(uri_path: &str) -> Option<String> {
    let segments: Vec<&str> = uri_path.trim_start_matches('/').split('/').collect();

    match segments.as_slice() {
        // The WebView keeps asking for `/media/<id>`; the backend serves those bytes from
        // its library preview route. Keeping the two spellings separate means the WebView
        // URL does not have to change when the backend route moves.
        ["media", file_id] => {
            check_segment(file_id)?;
            Some(format!("/api/v1/library/files/preview/{file_id}"))
        }
        _ => None,
    }
}

/// Whether one path segment is safe to forward.
///
/// Validated against its decoded form so an escaped traversal (`%2e%2e`) is caught; the
/// encoded form is what gets forwarded, since the backend decodes it itself.
fn check_segment(segment: &str) -> Option<()> {
    if segment.is_empty() {
        return None;
    }
    let decoded = percent_decode(segment);
    if decoded.is_empty()
        || decoded == "."
        || decoded == ".."
        || decoded.contains('/')
        || decoded.contains('\\')
        || decoded.contains('\0')
    {
        return None;
    }
    Some(())
}

/// Decode `%XX` escapes, for validation only.
///
/// Lossy on purpose: this exists to see what a segment really says, not to reconstruct it.
/// An invalid escape is left as written, which cannot smuggle a separator past the checks
/// above — the bytes it would have to produce are exactly what is being looked for.
fn percent_decode(value: &str) -> String {
    let bytes = value.as_bytes();
    let mut out: Vec<u8> = Vec::with_capacity(bytes.len());
    let mut index = 0;

    while index < bytes.len() {
        if bytes[index] == b'%' && index + 2 < bytes.len() {
            let hex = std::str::from_utf8(&bytes[index + 1..index + 3]).ok();
            if let Some(byte) = hex.and_then(|hex| u8::from_str_radix(hex, 16).ok()) {
                out.push(byte);
                index += 3;
                continue;
            }
        }
        out.push(bytes[index]);
        index += 1;
    }

    String::from_utf8_lossy(&out).into_owned()
}

/// Why a `fileseek://` request could not be answered.
#[derive(Debug, PartialEq, Eq)]
pub enum MediaError {
    /// The path is not one of the two media endpoints.
    NotMapped,
    /// The backend is not running, or published no connection file.
    Unreachable(String),
}

impl MediaError {
    /// The status the WebView sees.
    ///
    /// An unmapped path is 403 rather than 404: the resource is not missing, the request was
    /// refused. An unreachable backend is 503 — the same status the API client already reads
    /// as "up but not ready", so the UI's existing handling applies.
    pub fn status(&self) -> u16 {
        match self {
            MediaError::NotMapped => 403,
            MediaError::Unreachable(_) => 503,
        }
    }

    pub fn message(&self) -> String {
        match self {
            MediaError::NotMapped => "not a media path".to_string(),
            MediaError::Unreachable(detail) => detail.clone(),
        }
    }
}

/// Fetch what a `fileseek://` request asked for.
///
/// `range` is the player's `Range` header, forwarded so a seek pulls only the bytes it
/// needs. Split from the protocol registration so it is testable against a fake backend.
pub fn fetch(
    info: &ConnectionInfo,
    uri_path: &str,
    range: Option<&str>,
) -> Result<BinaryResponse, MediaError> {
    let backend_path = backend_path_for(uri_path).ok_or(MediaError::NotMapped)?;

    let headers: Vec<(String, String)> = range
        .map(|value| vec![("Range".to_string(), value.to_string())])
        .unwrap_or_default();

    perform_binary_request(info, "GET", &backend_path, &headers).map_err(MediaError::Unreachable)
}

/// Fetch for the current user's running backend, reading the connection file each time.
///
/// Re-read rather than cached because the backend rotates its token on every start: a
/// cached one would begin failing with 401 the moment the backend restarted.
pub fn fetch_for_current_backend(
    uri_path: &str,
    range: Option<&str>,
) -> Result<BinaryResponse, MediaError> {
    let connection_file = default_connection_file().map_err(MediaError::Unreachable)?;
    let info = ConnectionInfo::read(&connection_file)
        .map_err(|error| MediaError::Unreachable(error.to_string()))?;
    fetch(&info, uri_path, range)
}

/// Register the protocol on a Tauri builder.
///
/// Asynchronous: the responder is handed to a thread so a large video read does not block
/// the WebView's main thread while bytes are pulled from the backend (or from a NAS behind
/// it).
pub fn register<R: tauri::Runtime>(
    builder: tauri::Builder<R>,
) -> tauri::Builder<R> {
    builder.register_asynchronous_uri_scheme_protocol(SCHEME, |_app, request, responder| {
        let uri_path = request.uri().path().to_string();
        let range = request
            .headers()
            .get("Range")
            .and_then(|value| value.to_str().ok())
            .map(str::to_string);

        std::thread::spawn(move || {
            responder.respond(build_response(&uri_path, range.as_deref()));
        });
    })
}

/// Turn a fetch into the HTTP response the WebView receives.
fn build_response(uri_path: &str, range: Option<&str>) -> tauri::http::Response<Vec<u8>> {
    match fetch_for_current_backend(uri_path, range) {
        Ok(response) => {
            let mut builder = tauri::http::Response::builder()
                .status(response.status)
                .header("Content-Type", response.content_type)
                // So a player knows it may seek at all.
                .header("Accept-Ranges", "bytes");
            if let Some(content_range) = response.content_range {
                builder = builder.header("Content-Range", content_range);
            }
            builder
                .body(response.body)
                .unwrap_or_else(|_| error_response(500, "could not build the response"))
        }
        Err(error) => error_response(error.status(), &error.message()),
    }
}

fn error_response(status: u16, message: &str) -> tauri::http::Response<Vec<u8>> {
    tauri::http::Response::builder()
        .status(status)
        .header("Content-Type", "text/plain; charset=utf-8")
        .body(message.as_bytes().to_vec())
        .expect("a static error response is always well-formed")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_media_path_maps_to_the_library_preview_endpoint() {
        assert_eq!(
            backend_path_for("/media/file-1").unwrap(),
            "/api/v1/library/files/preview/file-1",
        );
    }

    #[test]
    fn an_id_with_dots_is_allowed() {
        // Ids are built from filenames, so a dot is ordinary — only a traversal is not.
        assert_eq!(
            backend_path_for("/media/file-report.v2.pdf").unwrap(),
            "/api/v1/library/files/preview/file-report.v2.pdf",
        );
    }

    #[test]
    fn a_percent_encoded_id_is_forwarded_as_written() {
        // The backend decodes it; re-encoding here would risk a different escaping of the
        // same name.
        assert_eq!(
            backend_path_for("/media/file-%E7%8C%AB.jpg").unwrap(),
            "/api/v1/library/files/preview/file-%E7%8C%AB.jpg",
        );
    }

    #[test]
    fn a_path_that_is_not_a_media_endpoint_is_refused() {
        // The whole point: this must not become a proxy for the rest of the API.
        for path in [
            "/search",
            "/tasks",
            "/ingest",
            "/health",
            "/",
            "",
            "/media",
            "/media/a/b",
            // Thumbnails were mapped once, but the backend never served them: it has no
            // thumbnail generation at all. Refused here rather than forwarded to a 404.
            "/thumbnails/vid-1/seg-2",
            "/thumbnails/a",
            "/thumbnails/a/b/c",
            "/Media/file-1",
        ] {
            assert!(backend_path_for(path).is_none(), "{path} should be refused");
        }
    }

    #[test]
    fn a_traversal_segment_is_refused() {
        for path in [
            "/media/..",
            "/media/.",
        ] {
            assert!(backend_path_for(path).is_none(), "{path} should be refused");
        }
    }

    #[test]
    fn an_escaped_traversal_is_refused() {
        // Validated against the decoded form, so `%2e%2e` cannot slip past.
        for path in [
            "/media/%2e%2e",
            "/media/%2E%2E",
            "/media/a%2Fb",
            "/media/a%5Cb",
            "/media/a%00b",
        ] {
            assert!(backend_path_for(path).is_none(), "{path} should be refused");
        }
    }

    #[test]
    fn an_empty_segment_is_refused() {
        assert!(backend_path_for("/media/").is_none());
    }

    #[test]
    fn percent_decoding_reads_what_a_segment_really_says() {
        assert_eq!(percent_decode("a%2Fb"), "a/b");
        assert_eq!(percent_decode("%2e%2e"), "..");
        assert_eq!(percent_decode("plain"), "plain");
        // An invalid escape is left alone rather than dropped.
        assert_eq!(percent_decode("100%"), "100%");
        assert_eq!(percent_decode("%zz"), "%zz");
    }

    #[test]
    fn an_unmapped_path_is_refused_without_reaching_the_backend() {
        // Port 1 answers nothing, so a 503 here would mean a request was attempted.
        let info = ConnectionInfo { port: 1, token: "t".to_string() };

        let error = fetch(&info, "/search", None).unwrap_err();

        assert_eq!(error, MediaError::NotMapped);
        assert_eq!(error.status(), 403);
    }

    #[test]
    fn an_unreachable_backend_is_reported_as_unavailable() {
        let info = ConnectionInfo { port: 1, token: "t".to_string() };

        let error = fetch(&info, "/media/file-1", None).unwrap_err();

        assert!(matches!(error, MediaError::Unreachable(_)));
        // The status the API client already reads as "up but not ready".
        assert_eq!(error.status(), 503);
    }

    #[test]
    fn an_unmapped_path_yields_a_403_response() {
        let response = build_response("/search", None);

        assert_eq!(response.status(), 403);
    }
}
