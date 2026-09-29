#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CloseDecision {
    HideToTray,
    AllowClose,
}

pub fn decide_close(window_label: &str, main_window_label: &str) -> CloseDecision {
    if window_label == main_window_label {
        CloseDecision::HideToTray
    } else {
        CloseDecision::AllowClose
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn main_window_close_is_hidden() {
        assert_eq!(decide_close("main", "main"), CloseDecision::HideToTray);
    }

    #[test]
    fn other_window_close_is_allowed() {
        assert_eq!(decide_close("settings", "main"), CloseDecision::AllowClose);
    }
}
