mod preview_protocol;
mod import_stream;

use preview_protocol::{connection_file_path, load_connection, PreviewTransportState};

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let transport_state = PreviewTransportState {
        connection: load_connection(&connection_file_path()),
    };
    let protocol_state = transport_state.clone();

    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .manage(transport_state)
        .invoke_handler(tauri::generate_handler![
            import_stream::open_import_event_stream
        ])
        .register_uri_scheme_protocol("fileseek-preview", move |_context, request| {
            preview_protocol::handle_preview_request(&protocol_state, &request)
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
