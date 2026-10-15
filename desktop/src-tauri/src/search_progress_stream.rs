use std::collections::HashMap;
use std::io::Read;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};

use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Emitter, State};

use crate::preview_protocol::{backend_url, BackendConnection};

const TOKEN_HEADER: &str = "X-FileSeek-Token";
const SEARCH_PROGRESS_EVENT_NAME: &str = "search-progress-chunk";
const SEARCH_PROGRESS_STREAM_PATH: &str = "/api/v1/search/enhanced/stream";

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SearchProgressStreamRequest {
    pub path: String,
    pub body: String,
    pub stream_id: String,
}

#[derive(Clone, Serialize)]
pub struct SearchProgressChunkPayload {
    pub stream_id: String,
    pub chunk: String,
}

#[derive(Default)]
pub struct SearchProgressStreams {
    cancels: Mutex<HashMap<String, Arc<AtomicBool>>>,
}

impl SearchProgressStreams {
    fn register(&self, stream_id: &str) -> Arc<AtomicBool> {
        let cancel = Arc::new(AtomicBool::new(false));
        self.cancels
            .lock()
            .expect("search progress stream registry poisoned")
            .insert(stream_id.to_owned(), cancel.clone());
        cancel
    }

    fn cancel(&self, stream_id: &str) -> bool {
        self.cancels
            .lock()
            .expect("search progress stream registry poisoned")
            .get(stream_id)
            .map(|cancel| {
                cancel.store(true, Ordering::SeqCst);
                true
            })
            .unwrap_or(false)
    }

    fn remove(&self, stream_id: &str) {
        self.cancels
            .lock()
            .expect("search progress stream registry poisoned")
            .remove(stream_id);
    }
}

#[tauri::command]
pub async fn open_search_progress_stream(
    app: AppHandle,
    streams: State<'_, SearchProgressStreams>,
    request: SearchProgressStreamRequest,
) -> Result<(), String> {
    if !is_approved_search_progress_stream_path(&request.path) {
        return Err("Search progress stream path is not allowed".to_owned());
    }

    let stream_id = request.stream_id.clone();
    let cancel = streams.register(&request.stream_id);
    let outcome = tauri::async_runtime::spawn_blocking(move || {
        read_search_progress_stream(app, request, cancel)
    })
    .await
    .map_err(|error| error.to_string())?;
    streams.remove(&stream_id);
    outcome
}

#[tauri::command]
pub fn cancel_search_progress_stream(
    streams: State<'_, SearchProgressStreams>,
    stream_id: String,
) -> Result<bool, String> {
    Ok(streams.cancel(&stream_id))
}

fn read_search_progress_stream(
    app: AppHandle,
    request: SearchProgressStreamRequest,
    cancel: Arc<AtomicBool>,
) -> Result<(), String> {
    let connection = load_search_progress_connection()?;
    let url = backend_url(&connection, &request.path);
    let response = ureq::post(&url)
        .set(TOKEN_HEADER, connection.token.as_str())
        .set("Accept", "text/event-stream")
        .set("Content-Type", "application/json")
        .send_string(&request.body)
        .map_err(|error| error.to_string())?;

    let mut reader = response.into_reader();
    let mut buffer = [0_u8; 8192];
    loop {
        if cancel.load(Ordering::SeqCst) {
            break;
        }
        let read = reader
            .read(&mut buffer)
            .map_err(|error| error.to_string())?;
        if read == 0 {
            break;
        }
        let chunk = String::from_utf8_lossy(&buffer[..read]).to_string();
        let payload = SearchProgressChunkPayload {
            stream_id: request.stream_id.clone(),
            chunk,
        };
        app.emit(SEARCH_PROGRESS_EVENT_NAME, payload)
            .map_err(|error| error.to_string())?;
    }
    Ok(())
}

fn load_search_progress_connection() -> Result<BackendConnection, String> {
    crate::preview_protocol::load_connection(&crate::preview_protocol::connection_file_path())
        .ok_or_else(|| "Backend connection is unavailable".to_owned())
}

pub fn is_approved_search_progress_stream_path(path: &str) -> bool {
    path == SEARCH_PROGRESS_STREAM_PATH
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn allows_only_the_search_progress_stream_path() {
        assert!(is_approved_search_progress_stream_path(
            "/api/v1/search/enhanced/stream"
        ));
        assert!(!is_approved_search_progress_stream_path(
            "/api/v1/search/enhanced/stream?x=1"
        ));
        assert!(!is_approved_search_progress_stream_path(
            "/api/v1/library/files/import/import-1/events"
        ));
        assert!(!is_approved_search_progress_stream_path(
            "/api/v1/search/../enhanced/stream"
        ));
    }

    #[test]
    fn event_payload_does_not_expose_the_backend_token_or_request_body() {
        let payload = SearchProgressChunkPayload {
            stream_id: "stream-1".to_owned(),
            chunk: "event: progress\ndata: {}\n\n".to_owned(),
        };
        let value = serde_json::to_value(&payload).expect("payload");

        assert!(value.get("token").is_none());
        assert!(value.get("body").is_none());
        assert_eq!(value["stream_id"], "stream-1");
        assert_eq!(value["chunk"], "event: progress\ndata: {}\n\n");
    }

    #[test]
    fn cancellation_registry_marks_and_removes_streams() {
        let streams = SearchProgressStreams::default();
        let cancel = streams.register("stream-1");
        assert!(!cancel.load(Ordering::SeqCst));

        assert!(streams.cancel("stream-1"));
        assert!(cancel.load(Ordering::SeqCst));

        streams.remove("stream-1");
        assert!(!streams.cancel("stream-1"));
    }
}
