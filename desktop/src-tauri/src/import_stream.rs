use std::io::Read;

use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Emitter};

use crate::preview_protocol::{backend_url, BackendConnection};

const TOKEN_HEADER: &str = "X-FileSeek-Token";
const IMPORT_EVENT_NAME: &str = "import-event-chunk";

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ImportStreamRequest {
    pub path: String,
    pub last_event_id: u64,
    pub stream_id: String,
}

#[derive(Clone, Serialize)]
pub struct ImportEventChunkPayload {
    pub stream_id: String,
    pub chunk: String,
}

#[tauri::command]
pub async fn open_import_event_stream(
    app: AppHandle,
    request: ImportStreamRequest,
) -> Result<(), String> {
    if !is_approved_import_stream_path(&request.path) {
        return Err("Import event path is not allowed".to_owned());
    }

    tauri::async_runtime::spawn_blocking(move || read_import_stream(app, request))
        .await
        .map_err(|error| error.to_string())?
}

fn read_import_stream(app: AppHandle, request: ImportStreamRequest) -> Result<(), String> {
    let connection = load_import_connection()?;
    let url = backend_url(&connection, &request.path);
    let response = ureq::get(&url)
        .set(TOKEN_HEADER, connection.token.as_str())
        .set("Accept", "text/event-stream")
        .set("Last-Event-ID", &request.last_event_id.to_string())
        .call()
        .map_err(|error| error.to_string())?;

    let mut reader = response.into_reader();
    let mut buffer = [0_u8; 8192];
    loop {
        let read = reader
            .read(&mut buffer)
            .map_err(|error| error.to_string())?;
        if read == 0 {
            break;
        }
        let chunk = String::from_utf8_lossy(&buffer[..read]).to_string();
        let payload = ImportEventChunkPayload {
            stream_id: request.stream_id.clone(),
            chunk,
        };
        app.emit(IMPORT_EVENT_NAME, payload)
            .map_err(|error| error.to_string())?;
    }
    Ok(())
}

fn load_import_connection() -> Result<BackendConnection, String> {
    crate::preview_protocol::load_connection(&crate::preview_protocol::connection_file_path())
        .ok_or_else(|| "Backend connection is unavailable".to_owned())
}

pub fn is_approved_import_stream_path(path: &str) -> bool {
    if path.split_once('?').is_some() {
        return false;
    }
    let segments: Vec<&str> = path.trim_matches('/').split('/').collect();
    if segments.len() != 7 {
        return false;
    }
    segments[..5] == ["api", "v1", "library", "files", "import"]
        && !segments[5].is_empty()
        && !segments[5].contains("..")
        && segments[6] == "events"
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn allows_only_import_event_streams() {
        assert!(is_approved_import_stream_path(
            "/api/v1/library/files/import/import-1/events"
        ));
        assert!(!is_approved_import_stream_path(
            "/api/v1/library/files/import/import-1/events?x=1"
        ));
        assert!(!is_approved_import_stream_path(
            "/api/v1/library/files/file-1/thumbnail"
        ));
        assert!(!is_approved_import_stream_path(
            "/api/v1/library/files/import/../events"
        ));
    }

    #[test]
    fn event_payload_does_not_expose_the_backend_token() {
        let payload = ImportEventChunkPayload {
            stream_id: "stream-1".to_owned(),
            chunk: "id: 1\n".to_owned(),
        };
        let value = serde_json::to_value(&payload).expect("payload");

        assert!(value.get("token").is_none());
        assert_eq!(value["stream_id"], "stream-1");
        assert_eq!(value["chunk"], "id: 1\n");
    }
}
