mod autostart;
mod connection;
mod lifecycle;
mod media;
mod sidecar;
mod test_support;
mod tray;

use connection::home_dir;
use lifecycle::{decide_close, BackendState, CloseDecision};
use sidecar::{BackendCommand, Sidecar};
use std::path::PathBuf;
use std::time::Duration;
use tauri::{Manager, RunEvent, WindowEvent};

const BACKEND_READY_TIMEOUT: Duration = Duration::from_secs(30);

fn start_backend() -> Option<Sidecar> {
    let exe = std::env::current_exe().ok()?;
    let repo_root = sidecar::repo_root_from_exe(&exe)
        .unwrap_or_else(|| std::env::current_dir().unwrap_or_default());
    let command = BackendCommand::resolve(&repo_root);

    let home = home_dir().unwrap_or_else(|| PathBuf::from("."));
    let connection_file = sidecar::connection_file_path(&home);

    match Sidecar::start(&command, &connection_file, BACKEND_READY_TIMEOUT) {
        Ok(sidecar) => {
            println!("FileSeek backend ready on 127.0.0.1:{}", sidecar.port());
            Some(sidecar)
        }
        Err(error) => {
            eprintln!("failed to start FileSeek backend: {error}");
            None
        }
    }
}

// Learn more about Tauri commands at https://tauri.app/develop/calling-rust/
#[tauri::command]
fn greet(name: &str) -> String {
    format!("Hello, {}! You've been greeted from Rust!", name)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    // The `fileseek://` protocol is registered before anything else so the WebView can
    // resolve image and video sources as soon as it loads. It is what carries the backend's
    // token on requests `<img src>` and `<video src>` cannot set a header on (see
    // `media.rs`).
    #[allow(unused_mut)]
    let mut builder = media::register(tauri::Builder::default())
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![
            greet,
            connection::api_request,
            autostart::autostart_status,
            autostart::set_autostart
        ])
        .setup(|app| {
            app.manage(BackendState::new(start_backend()));
            tray::build(app.handle())?;
            Ok(())
        })
        .on_window_event(|window, event| {
            // Closing the main window hides it instead of destroying it, so the app stays
            // in the tray and the backend keeps working through the queue
            // (`desktop-client`: 关闭主窗口 → 应用保留在托盘中，后端服务继续处理排队任务).
            //
            // Without this the last window closing would end the process, taking the
            // backend with it. Quitting deliberately goes through the tray's quit item.
            if let WindowEvent::CloseRequested { api, .. } = event {
                if decide_close(window.label(), tray::MAIN_WINDOW) == CloseDecision::HideToTray {
                    api.prevent_close();
                    let _ = window.hide();
                }
            }
        });

    // Debug builds only: the MCP bridge exposes a WebSocket that can run arbitrary JS in the
    // WebView, so it is bound to loopback rather than the plugin's default `0.0.0.0` to keep
    // it off the local network.
    #[cfg(debug_assertions)]
    {
        builder = builder.plugin(
            tauri_plugin_mcp_bridge::Builder::new()
                .bind_address("127.0.0.1")
                .build(),
        );
    }

    builder
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app_handle, event| {
            // Reached when the tray's quit item calls `app.exit(0)`, not when the window
            // is closed — that path is intercepted above. So an exit request here means
            // the user asked to quit, and the backend is stopped
            // (`desktop-client`: 从托盘退出 → 后端服务停止).
            if let RunEvent::ExitRequested { .. } = event {
                app_handle.state::<BackendState>().stop();
            }
        });
}
