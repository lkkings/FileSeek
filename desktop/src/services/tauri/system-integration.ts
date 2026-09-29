import { invoke } from "@tauri-apps/api/core";

import { isTauriRuntime } from "./api";

export interface SystemIntegrationStatus {
  silentStartupEnabled: boolean;
  fileManagerIntegrationEnabled: boolean;
  fileManagerIntegrationSupported: boolean;
  finderExtensionApprovalRequired: boolean;
}

export const defaultSystemIntegrationStatus: SystemIntegrationStatus = {
  silentStartupEnabled: false,
  fileManagerIntegrationEnabled: false,
  fileManagerIntegrationSupported: true,
  finderExtensionApprovalRequired: false,
};

export function getSystemIntegrationStatus(): Promise<SystemIntegrationStatus> {
  if (!isTauriRuntime()) {
    return Promise.resolve(defaultSystemIntegrationStatus);
  }
  return invoke<SystemIntegrationStatus>("get_system_integration_status");
}

export function setSilentStartup(enabled: boolean): Promise<SystemIntegrationStatus> {
  if (!isTauriRuntime()) {
    return Promise.resolve({
      ...defaultSystemIntegrationStatus,
      silentStartupEnabled: enabled,
    });
  }
  return invoke<SystemIntegrationStatus>("set_silent_startup", { enabled });
}

export function setFileManagerIntegration(enabled: boolean): Promise<SystemIntegrationStatus> {
  if (!isTauriRuntime()) {
    return Promise.resolve({
      ...defaultSystemIntegrationStatus,
      fileManagerIntegrationEnabled: enabled,
    });
  }
  return invoke<SystemIntegrationStatus>("set_file_manager_integration", { enabled });
}
