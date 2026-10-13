use std::path::Path;
use std::time::Duration;

use tauri::tray::{MouseButton, MouseButtonState, TrayIconEvent};
use tauri::Manager;

use crate::preview_protocol::{backend_url, load_connection, BackendConnection};

pub const MAIN_WINDOW: &str = "main";
pub const MENU_OPEN: &str = "open";
pub const MENU_BACKEND_STATUS: &str = "backend-status";
pub const MENU_QUIT: &str = "quit";
const POLL_INTERVAL: Duration = Duration::from_secs(2);

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TrayAction {
    OpenWindow,
    Ignore,
    Quit,
}

pub fn should_show_for_icon_event(event: &TrayIconEvent) -> bool {
    match event {
        TrayIconEvent::Click {
            button,
            button_state,
            ..
        } => should_show_for_click(*button, *button_state),
        TrayIconEvent::DoubleClick { button, .. } => should_show_for_double_click(*button),
        _ => false,
    }
}

pub fn should_show_for_click(button: MouseButton, button_state: MouseButtonState) -> bool {
    button == MouseButton::Left && button_state == MouseButtonState::Up
}

pub fn should_show_for_double_click(button: MouseButton) -> bool {
    button == MouseButton::Left
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum BackendStatus {
    Connected,
    Disconnected,
}

pub fn action_for(menu_id: &str) -> TrayAction {
    match menu_id {
        MENU_OPEN => TrayAction::OpenWindow,
        MENU_QUIT => TrayAction::Quit,
        _ => TrayAction::Ignore,
    }
}

pub fn backend_status_label(status: BackendStatus) -> &'static str {
    match status {
        BackendStatus::Connected => "后端已连接",
        BackendStatus::Disconnected => "后端未连接",
    }
}

pub fn tooltip(status: BackendStatus) -> String {
    format!("FileSeek — {}", backend_status_label(status))
}

pub fn show_main_window<R: tauri::Runtime>(app: &tauri::AppHandle<R>) {
    #[cfg(target_os = "macos")]
    let _ = app.set_activation_policy(tauri::ActivationPolicy::Regular);

    if let Some(window) = app.get_webview_window(MAIN_WINDOW) {
        let _ = window.show();
        let _ = window.unminimize();
        let _ = window.set_focus();
    }
}

pub fn main_window_visible<R: tauri::Runtime>(app: &tauri::AppHandle<R>) -> bool {
    app.get_webview_window(MAIN_WINDOW)
        .and_then(|window| window.is_visible().ok())
        .unwrap_or(false)
}

/// Sends the main window to the tray, as closing it does; the app keeps working (a
/// first-run download, say) and the tray brings it back.
#[tauri::command]
pub fn hide_to_tray(app: tauri::AppHandle) {
    if let Some(window) = app.get_webview_window(MAIN_WINDOW) {
        let _ = window.hide();
    }
}

pub fn set_hidden_activation_policy<R: tauri::Runtime>(_app: &tauri::AppHandle<R>) {
    #[cfg(target_os = "macos")]
    let _ = app.set_activation_policy(tauri_activation_policy(activation_policy(true)));
}

#[cfg(target_os = "macos")]
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AppActivationPolicy {
    Accessory,
    Regular,
}

#[cfg(target_os = "macos")]
pub fn activation_policy(hidden: bool) -> AppActivationPolicy {
    if hidden {
        AppActivationPolicy::Accessory
    } else {
        AppActivationPolicy::Regular
    }
}

#[cfg(target_os = "macos")]
fn tauri_activation_policy(policy: AppActivationPolicy) -> tauri::ActivationPolicy {
    match policy {
        AppActivationPolicy::Accessory => tauri::ActivationPolicy::Accessory,
        AppActivationPolicy::Regular => tauri::ActivationPolicy::Regular,
    }
}

pub fn build(app: &tauri::AppHandle) -> tauri::Result<()> {
    use tauri::menu::{MenuBuilder, MenuItemBuilder};
    use tauri::tray::TrayIconBuilder;

    let initial_status = backend_status(&crate::preview_protocol::connection_file_path());
    let open = MenuItemBuilder::with_id(MENU_OPEN, "打开 FileSeek").build(app)?;
    let backend =
        MenuItemBuilder::with_id(MENU_BACKEND_STATUS, backend_status_label(initial_status))
            .enabled(false)
            .build(app)?;
    let quit = MenuItemBuilder::with_id(MENU_QUIT, "退出").build(app)?;

    let menu = MenuBuilder::new(app)
        .item(&open)
        .separator()
        .item(&backend)
        .separator()
        .item(&quit)
        .build()?;

    let tray = TrayIconBuilder::with_id("main-tray")
        .menu(&menu)
        .show_menu_on_left_click(false)
        .tooltip(tooltip(initial_status))
        .icon(app.default_window_icon().cloned().ok_or_else(|| {
            tauri::Error::InvalidIcon(std::io::Error::other("no default window icon"))
        })?)
        .on_menu_event(|app, event| match action_for(event.id().as_ref()) {
            TrayAction::OpenWindow => show_main_window(app),
            TrayAction::Quit => app.exit(0),
            TrayAction::Ignore => {}
        })
        .on_tray_icon_event(|tray, event| {
            if should_show_for_icon_event(&event) {
                show_main_window(tray.app_handle());
            }
        })
        .build(app)?;

    start_backend_status_polling(tray, backend);
    Ok(())
}

pub fn backend_status(connection_file: &Path) -> BackendStatus {
    backend_status_with(connection_file, health_check_ok)
}

pub fn backend_status_with<F>(connection_file: &Path, health_check: F) -> BackendStatus
where
    F: Fn(&BackendConnection) -> bool,
{
    let connection = load_connection(connection_file);
    connection.map_or(BackendStatus::Disconnected, |connection| {
        health_check(&connection)
            .then_some(BackendStatus::Connected)
            .unwrap_or(BackendStatus::Disconnected)
    })
}

fn health_check_ok(connection: &BackendConnection) -> bool {
    ureq::get(&backend_url(connection, "/health"))
        .timeout(Duration::from_secs(1))
        .call()
        .ok()
        .filter(|response| response.status() == 200)
        .and_then(|response| response.into_json::<serde_json::Value>().ok())
        .and_then(|body| {
            body.get("data")
                .and_then(|data| data.get("status"))
                .and_then(|status| status.as_str().map(str::to_owned))
        })
        .as_deref()
        == Some("ok")
}

fn start_backend_status_polling<R: tauri::Runtime>(
    tray: tauri::tray::TrayIcon<R>,
    backend_item: tauri::menu::MenuItem<R>,
) {
    std::thread::spawn(move || loop {
        std::thread::sleep(POLL_INTERVAL);
        let status = backend_status(&crate::preview_protocol::connection_file_path());
        let _ = backend_item.set_text(backend_status_label(status));
        let _ = tray.set_tooltip(Some(tooltip(status)));
    });
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use std::path::PathBuf;

    fn temp_connection_file() -> PathBuf {
        let mut path = std::env::temp_dir();
        path.push(format!("fileseek-tray-test-{}", std::process::id()));
        let _ = fs::remove_dir_all(&path);
        fs::create_dir_all(&path).expect("temp dir");
        path.join("connection.json")
    }

    fn write_connection(path: &Path, port: u16) {
        let contents = format!(r#"{{"port":{},"token":"test-token"}}"#, port);
        fs::write(path, contents).expect("connection file");
    }

    #[test]
    fn open_and_quit_map_to_actions() {
        assert_eq!(action_for(MENU_OPEN), TrayAction::OpenWindow);
        assert_eq!(action_for(MENU_QUIT), TrayAction::Quit);
    }

    #[test]
    fn status_menu_item_is_not_clickable() {
        assert_eq!(action_for(MENU_BACKEND_STATUS), TrayAction::Ignore);
    }

    #[test]
    fn backend_labels_and_tooltips_are_distinct() {
        assert_eq!(backend_status_label(BackendStatus::Connected), "后端已连接");
        assert_eq!(
            backend_status_label(BackendStatus::Disconnected),
            "后端未连接"
        );
        assert_eq!(
            tooltip(BackendStatus::Disconnected),
            "FileSeek — 后端未连接"
        );
    }

    #[cfg(target_os = "macos")]
    #[test]
    fn activation_policy_transitions_between_hidden_and_visible() {
        assert_eq!(activation_policy(true), AppActivationPolicy::Accessory);
        assert_eq!(activation_policy(false), AppActivationPolicy::Regular);
    }

    #[test]
    fn left_click_and_left_double_click_restore_the_window() {
        assert!(should_show_for_click(
            MouseButton::Left,
            MouseButtonState::Up
        ));
        assert!(!should_show_for_click(
            MouseButton::Left,
            MouseButtonState::Down
        ));
        assert!(!should_show_for_click(
            MouseButton::Right,
            MouseButtonState::Up
        ));
        assert!(should_show_for_double_click(MouseButton::Left));
        assert!(!should_show_for_double_click(MouseButton::Right));
    }

    #[test]
    fn missing_connection_reports_disconnected() {
        let path = temp_connection_file();
        assert_eq!(backend_status(&path), BackendStatus::Disconnected);
    }

    #[test]
    fn unhealthy_backend_reports_disconnected() {
        let path = temp_connection_file();
        write_connection(&path, 0);
        assert_eq!(
            backend_status_with(&path, |_| false),
            BackendStatus::Disconnected
        );
    }

    #[test]
    fn healthy_backend_reports_connected() {
        let path = temp_connection_file();
        write_connection(&path, 0);
        assert_eq!(
            backend_status_with(&path, |_| true),
            BackendStatus::Connected
        );
    }
}
