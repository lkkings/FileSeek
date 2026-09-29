mod autostart;
mod file_manager;
mod import_stream;
mod lifecycle;
mod preview_protocol;
mod startup_args;
mod system_import;
mod system_integration;
mod tray;

use std::path::Path;

use preview_protocol::{connection_file_path, load_connection, PreviewTransportState};
use tauri::{Emitter, WindowEvent};

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let startup_intent = startup_args::parse(std::env::args());
    let startup_import = system_import::request_from_args(
        std::env::args(),
        &std::env::current_dir().unwrap_or_default(),
    );
    let pending_import = std::sync::Mutex::new(startup_import);
    let transport_state = PreviewTransportState {
        connection: load_connection(&connection_file_path()),
    };
    let protocol_state = transport_state.clone();

    tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(
            |app, args, current_directory| {
                let request = system_import::request_from_args(args, Path::new(&current_directory));
                if request.is_none() {
                    tray::show_main_window(app);
                    return;
                }

                tray::show_main_window(app);
                let _ = app.emit(system_import::EVENT_NAME, request);
            },
        ))
        .plugin(tauri_plugin_opener::init())
        .manage(transport_state)
        .manage(pending_import)
        .invoke_handler(tauri::generate_handler![
            import_stream::open_import_event_stream,
            system_integration::get_system_integration_status,
            system_integration::set_silent_startup,
            system_integration::set_file_manager_integration,
            system_import::take_pending_system_import
        ])
        .setup(move |app| {
            tray::build(app.handle())?;
            if startup_args::visibility(&startup_intent) == startup_args::StartupVisibility::Hide {
                tray::set_hidden_activation_policy(app.handle());
            } else {
                tray::show_main_window(app.handle());
            }
            Ok(())
        })
        .on_window_event(|window, event| {
            if let WindowEvent::CloseRequested { api, .. } = event {
                if lifecycle::decide_close(window.label(), tray::MAIN_WINDOW)
                    == lifecycle::CloseDecision::HideToTray
                {
                    api.prevent_close();
                    let _ = window.hide();
                }
            }
        })
        .register_uri_scheme_protocol("fileseek-preview", move |_context, request| {
            preview_protocol::handle_preview_request(&protocol_state, &request)
        })
        .build(tauri::generate_context!())
        .expect("error while building the tauri application")
        .run(|app, event| {
            #[cfg(target_os = "macos")]
            if let tauri::RunEvent::Reopen {
                has_visible_windows,
                ..
            } = event
            {
                if !has_visible_windows {
                    tray::show_main_window(app);
                }
            }
        });
}
