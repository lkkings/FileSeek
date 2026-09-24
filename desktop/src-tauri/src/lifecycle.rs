//! What closing the window means, and what quitting means.
//!
//! These are two different things, and the difference is a spec requirement
//! (`desktop-client`: 关闭主窗口 **MUST NOT** 终止后端服务；退出操作 **MUST** 同时停止后端服务).
//!
//! - Closing the main window hides it. The app stays in the tray and the backend keeps
//!   working through the queue.
//! - Quitting from the tray stops the backend, so unfinished tasks are left durably queued
//!   for the next start rather than being processed by an orphaned process.
//!
//! The decision is a function and the backend handle is a plain struct, so both paths are
//! testable without a window or an event loop.

use std::sync::Mutex;

use crate::sidecar::Sidecar;

/// What to do with a window's close request.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CloseDecision {
    /// Keep the window alive but out of sight, leaving the backend running.
    HideToTray,
    /// Let the window close normally.
    AllowClose,
}

/// Decide what a close request on `window_label` should do.
///
/// Only the main window is held back: it is the one whose closing would otherwise end the
/// process. Any other window (a future settings or player window) closes normally.
pub fn decide_close(window_label: &str, main_window_label: &str) -> CloseDecision {
    if window_label == main_window_label {
        CloseDecision::HideToTray
    } else {
        CloseDecision::AllowClose
    }
}

/// Holds the running backend so quitting can stop it.
///
/// `None` when the backend failed to start, which is not fatal: the UI still runs and
/// reports the failure (task 15.7 owns surfacing it).
pub struct BackendState(Mutex<Option<Sidecar>>);

impl BackendState {
    pub fn new(sidecar: Option<Sidecar>) -> Self {
        BackendState(Mutex::new(sidecar))
    }

    /// Whether a backend is currently held.
    pub fn is_running(&self) -> bool {
        self.0.lock().map(|guard| guard.is_some()).unwrap_or(false)
    }

    /// The backend's pid, while one is held.
    pub fn pid(&self) -> Option<u32> {
        self.0.lock().ok().and_then(|guard| guard.as_ref().map(Sidecar::pid))
    }

    /// Stop the backend and release it. Idempotent: quitting twice is not an error.
    ///
    /// The handle is taken out of the mutex before being stopped so the lock is not held
    /// across the wait for the process to exit.
    pub fn stop(&self) {
        let taken = self.0.lock().ok().and_then(|mut guard| guard.take());
        if let Some(mut running) = taken {
            running.stop();
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::test_support::{is_alive, start_fake_sidecar};
    use crate::tray::MAIN_WINDOW;

    #[test]
    fn closing_the_main_window_hides_it_instead_of_closing() {
        assert_eq!(
            decide_close(MAIN_WINDOW, MAIN_WINDOW),
            CloseDecision::HideToTray
        );
    }

    #[test]
    fn closing_another_window_is_allowed() {
        assert_eq!(
            decide_close("settings", MAIN_WINDOW),
            CloseDecision::AllowClose
        );
    }

    #[test]
    fn closing_the_main_window_leaves_the_backend_running() {
        // desktop-client: 关闭主窗口 → 应用保留在托盘中，后端服务继续处理排队任务.
        let (sidecar, _dir) = start_fake_sidecar("lifecycle-close");
        let pid = sidecar.pid();
        let state = BackendState::new(Some(sidecar));

        // The close path decides to hide; it never touches the backend.
        assert_eq!(
            decide_close(MAIN_WINDOW, MAIN_WINDOW),
            CloseDecision::HideToTray
        );

        assert!(state.is_running(), "the backend handle should still be held");
        assert!(is_alive(pid), "process {pid} should still be running after a close");

        state.stop();
    }

    #[test]
    fn quitting_stops_the_backend() {
        // desktop-client: 从托盘退出 → 后端服务停止.
        let (sidecar, _dir) = start_fake_sidecar("lifecycle-quit");
        let pid = sidecar.pid();
        let state = BackendState::new(Some(sidecar));
        assert!(is_alive(pid), "the backend should be running before quit");

        state.stop();

        assert!(!state.is_running(), "the handle should have been released");
        assert!(!is_alive(pid), "process {pid} should have exited on quit");
    }

    #[test]
    fn stopping_twice_is_harmless() {
        let (sidecar, _dir) = start_fake_sidecar("lifecycle-twice");
        let state = BackendState::new(Some(sidecar));

        state.stop();
        state.stop();

        assert!(!state.is_running());
    }

    #[test]
    fn stopping_without_a_backend_is_harmless() {
        // The backend failed to start; quitting must not panic.
        let state = BackendState::new(None);

        state.stop();

        assert!(!state.is_running());
        assert_eq!(state.pid(), None);
    }
}
