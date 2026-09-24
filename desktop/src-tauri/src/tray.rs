//! The tray icon: the app's resident entry point.
//!
//! The tray carries three things (`desktop-client`: 常驻托盘与后端生命周期): an entry that
//! opens the main window, the number of tasks currently being processed, and quit.
//!
//! Closing the main window and quitting mean different things here. Closing hides the
//! window and leaves the backend running, so queued work keeps being processed; quitting
//! from the tray stops the backend. That split is the whole reason the window's close
//! request is intercepted rather than allowed to end the process.
//!
//! The decisions — what a menu id means, what the labels say, what the counts are — are
//! plain functions below, so they are tested without a display or an event loop. Only the
//! wiring in `build` needs a running Tauri app.

use std::time::Duration;

use serde::Deserialize;

use crate::connection::{perform_request, ConnectionInfo};

/// Menu item ids. Matched by string when a menu event arrives, so they are named here
/// rather than spelled out at each site.
pub const MENU_OPEN: &str = "open";
pub const MENU_PROCESSING: &str = "processing";
pub const MENU_QUIT: &str = "quit";

/// The window the tray opens. Tauri's default label, as `tauri.conf.json` sets none.
pub const MAIN_WINDOW: &str = "main";

/// How often the processing count is refreshed while the app is running.
pub const POLL_INTERVAL: Duration = Duration::from_secs(2);

/// What a tray menu selection means.
///
/// `Quit` is distinct from the window's close request: it is the one path that stops the
/// backend.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TrayAction {
    /// Show and focus the main window.
    OpenWindow,
    /// Stop the backend and exit.
    Quit,
    /// A click with no behaviour — the count is a label, not a button.
    Ignore,
}

/// Map a menu item id to what it does.
pub fn action_for(menu_id: &str) -> TrayAction {
    match menu_id {
        MENU_OPEN => TrayAction::OpenWindow,
        MENU_QUIT => TrayAction::Quit,
        _ => TrayAction::Ignore,
    }
}

/// How many tasks sit in each status, as `GET /tasks` reports them.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Deserialize)]
pub struct TaskCounts {
    #[serde(default)]
    pub queued: u32,
    #[serde(default)]
    pub processing: u32,
    #[serde(default)]
    pub completed: u32,
    #[serde(default)]
    pub failed: u32,
}

/// The menu line showing what is in flight.
///
/// Reads as a status line rather than a bare number, since a menu item with "3" in it
/// would not say what the 3 counts.
pub fn processing_label(counts: &TaskCounts) -> String {
    if counts.processing == 0 && counts.queued == 0 {
        return "空闲".to_string();
    }
    if counts.queued == 0 {
        return format!("处理中：{} 个任务", counts.processing);
    }
    format!("处理中：{} 个任务（排队 {}）", counts.processing, counts.queued)
}

/// The icon's hover text. Carries the app name, which the menu line does not need to.
pub fn tooltip(counts: &TaskCounts) -> String {
    if counts.processing == 0 && counts.queued == 0 {
        return "FileSeek — 空闲".to_string();
    }
    format!("FileSeek — {}", processing_label(counts))
}

/// Pull the counts out of a `GET /tasks` response body.
///
/// Returns `None` for a body that is not that shape, which the caller treats the same as
/// an unreachable backend: the tray keeps its previous label rather than showing a zero
/// that would read as "nothing is running".
pub fn counts_from_response(body: &str) -> Option<TaskCounts> {
    #[derive(Deserialize)]
    struct Envelope {
        data: Option<Data>,
    }
    #[derive(Deserialize)]
    struct Data {
        counts: TaskCounts,
    }

    let envelope: Envelope = serde_json::from_str(body).ok()?;
    Some(envelope.data?.counts)
}

/// Ask the backend how much work is in flight.
///
/// `page_size=1` because only the counts are wanted; the endpoint returns them whatever
/// the page asks for, so this avoids pulling a page of tasks to count them.
pub fn fetch_counts(info: &ConnectionInfo) -> Option<TaskCounts> {
    let response = perform_request(info, "GET", "/tasks?page_size=1", None).ok()?;
    if response.status != 200 {
        return None;
    }
    counts_from_response(&response.body)
}

/// Show the main window and bring it forward.
///
/// Used by the tray's open entry. The window was hidden rather than destroyed when it was
/// closed, so this shows the same window rather than building a new one.
pub fn show_main_window<R: tauri::Runtime>(app: &tauri::AppHandle<R>) {
    use tauri::Manager;

    if let Some(window) = app.get_webview_window(MAIN_WINDOW) {
        let _ = window.show();
        let _ = window.unminimize();
        let _ = window.set_focus();
    }
}

/// Build the tray icon and its menu, and start refreshing the count.
///
/// The count item is disabled: it reports state, and a clickable one would suggest
/// otherwise. `action_for` also maps it to `Ignore`, so neither path acts on it.
pub fn build(app: &tauri::AppHandle) -> tauri::Result<()> {
    use tauri::menu::{MenuBuilder, MenuItemBuilder};
    use tauri::tray::TrayIconBuilder;

    let open = MenuItemBuilder::with_id(MENU_OPEN, "打开 FileSeek").build(app)?;
    let processing = MenuItemBuilder::with_id(MENU_PROCESSING, processing_label(&TaskCounts::default()))
        .enabled(false)
        .build(app)?;
    let quit = MenuItemBuilder::with_id(MENU_QUIT, "退出").build(app)?;

    let menu = MenuBuilder::new(app)
        .item(&open)
        .separator()
        .item(&processing)
        .separator()
        .item(&quit)
        .build()?;

    let tray = TrayIconBuilder::with_id("main-tray")
        .menu(&menu)
        .tooltip(tooltip(&TaskCounts::default()))
        .icon(app.default_window_icon().cloned().ok_or_else(|| {
            tauri::Error::InvalidIcon(std::io::Error::other("no default window icon"))
        })?)
        .on_menu_event(|app, event| match action_for(event.id().as_ref()) {
            TrayAction::OpenWindow => show_main_window(app),
            // The one path that stops the backend. Closing the window does not come
            // here, which is what keeps queued work being processed after a close.
            TrayAction::Quit => app.exit(0),
            TrayAction::Ignore => {}
        })
        .build(app)?;

    start_count_polling(tray, processing);
    Ok(())
}

/// Refresh the count line and tooltip in the background.
///
/// A thread rather than an async task: `perform_request` is blocking, and the tray is the
/// only thing waiting on it.
fn start_count_polling<R: tauri::Runtime>(
    tray: tauri::tray::TrayIcon<R>,
    processing_item: tauri::menu::MenuItem<R>,
) {
    std::thread::spawn(move || {
        loop {
            std::thread::sleep(POLL_INTERVAL);

            let Ok(connection_file) = crate::connection::default_connection_file() else {
                continue;
            };
            let Ok(info) = ConnectionInfo::read(&connection_file) else {
                // The backend is not up yet, or is restarting. Leave the last label.
                continue;
            };
            let Some(counts) = fetch_counts(&info) else {
                continue;
            };

            let _ = processing_item.set_text(processing_label(&counts));
            let _ = tray.set_tooltip(Some(tooltip(&counts)));
        }
    });
}

#[cfg(test)]
mod tests {
    use super::*;

    fn counts(processing: u32, queued: u32) -> TaskCounts {
        TaskCounts { processing, queued, ..TaskCounts::default() }
    }

    #[test]
    fn open_and_quit_map_to_their_actions() {
        assert_eq!(action_for(MENU_OPEN), TrayAction::OpenWindow);
        assert_eq!(action_for(MENU_QUIT), TrayAction::Quit);
    }

    #[test]
    fn the_count_line_is_not_clickable() {
        // It is a label; clicking it must not open or quit anything.
        assert_eq!(action_for(MENU_PROCESSING), TrayAction::Ignore);
    }

    #[test]
    fn an_unknown_menu_id_does_nothing() {
        assert_eq!(action_for("something-else"), TrayAction::Ignore);
    }

    #[test]
    fn the_label_shows_the_number_being_processed() {
        // desktop-client: 有 3 个任务正在处理 → 托盘展示当前处理中的任务数量.
        let label = processing_label(&counts(3, 0));

        assert!(label.contains('3'), "label was {label}");
        assert_eq!(label, "处理中：3 个任务");
    }

    #[test]
    fn the_label_reports_idle_when_nothing_is_running() {
        assert_eq!(processing_label(&counts(0, 0)), "空闲");
    }

    #[test]
    fn the_label_mentions_the_queue_when_work_is_waiting() {
        let label = processing_label(&counts(2, 7));

        assert!(label.contains('2'), "label was {label}");
        assert!(label.contains('7'), "label was {label}");
    }

    #[test]
    fn queued_work_is_not_reported_as_idle() {
        // A bulk import that has not started yet is not "nothing happening".
        assert_ne!(processing_label(&counts(0, 5)), "空闲");
    }

    #[test]
    fn the_tooltip_names_the_app_and_the_state() {
        assert_eq!(tooltip(&counts(3, 0)), "FileSeek — 处理中：3 个任务");
        assert_eq!(tooltip(&counts(0, 0)), "FileSeek — 空闲");
    }

    #[test]
    fn counts_are_read_from_the_endpoint_envelope() {
        let body = r#"{
            "status": "success",
            "data": {
                "tasks": [],
                "counts": {"queued": 1, "processing": 3, "completed": 9, "failed": 2}
            },
            "error": null
        }"#;

        let parsed = counts_from_response(body).unwrap();

        assert_eq!(parsed.processing, 3);
        assert_eq!(parsed.queued, 1);
        assert_eq!(parsed.failed, 2);
    }

    #[test]
    fn an_error_envelope_yields_no_counts() {
        // Keeping the previous label beats showing 0, which would read as "idle".
        let body = r#"{"status": "error", "data": null, "error": "authentication required"}"#;

        assert!(counts_from_response(body).is_none());
    }

    #[test]
    fn an_unreadable_body_yields_no_counts() {
        assert!(counts_from_response("<html>nope</html>").is_none());
    }
}
