use serde::{Deserialize, Serialize};

use crate::{autostart, file_manager};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SystemIntegrationStatus {
    pub silent_startup_enabled: bool,
    pub file_manager_integration_enabled: bool,
    pub file_manager_integration_supported: bool,
    pub finder_extension_approval_required: bool,
}

impl Default for SystemIntegrationStatus {
    fn default() -> Self {
        Self {
            silent_startup_enabled: false,
            file_manager_integration_enabled: false,
            file_manager_integration_supported: true,
            finder_extension_approval_required: false,
        }
    }
}

fn current_status() -> Result<SystemIntegrationStatus, String> {
    let silent_startup_enabled = autostart::current()?.is_enabled()?;
    let file_manager_integration_enabled = file_manager::is_enabled()?;
    #[cfg(target_os = "macos")]
    let finder_extension_approval_required = file_manager::finder_extension_approval_required();
    #[cfg(not(target_os = "macos"))]
    let finder_extension_approval_required = false;
    Ok(SystemIntegrationStatus {
        silent_startup_enabled,
        file_manager_integration_enabled,
        file_manager_integration_supported: file_manager::is_supported()?,
        finder_extension_approval_required,
    })
}

#[tauri::command]
pub fn get_system_integration_status() -> Result<SystemIntegrationStatus, String> {
    current_status()
}

#[tauri::command]
pub fn set_silent_startup(enabled: bool) -> Result<SystemIntegrationStatus, String> {
    autostart::current()?.set(enabled)?;
    current_status()
}

#[tauri::command]
pub fn set_file_manager_integration(enabled: bool) -> Result<SystemIntegrationStatus, String> {
    if enabled && !file_manager::is_supported()? {
        return Err("file-manager integration is not available in this build".to_owned());
    }
    file_manager::set_integration(enabled)?;
    current_status()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_status_is_off_and_supported() {
        let status = SystemIntegrationStatus::default();
        assert!(!status.silent_startup_enabled);
        assert!(!status.file_manager_integration_enabled);
        assert!(status.file_manager_integration_supported);
    }

    #[test]
    fn file_manager_status_is_read_from_the_operating_system() {
        let enabled = file_manager::is_enabled().expect("state");
        let supported = file_manager::is_supported().expect("support");
        assert_eq!(enabled, file_manager::is_enabled().expect("state"));
        assert!(!enabled || supported);
    }
}
