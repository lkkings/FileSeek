import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";

import { isTauriRuntime } from "./api";

/** Mirrors `update::UpdateStatus` in `src-tauri/src/update.rs`. */
export type UpdatePhase =
  | "disabled"
  | "idle"
  | "checking"
  | "up_to_date"
  | "available"
  | "downloading"
  | "ready"
  | "failed";

export interface UpdateInfo {
  version: string;
  notes: string | null;
  /** Below Keygate's minimum supported version: the banner cannot be closed. */
  required: boolean;
  /** Keygate's message for a required update. */
  requiredMessage: string | null;
}

export interface UpdateStatus {
  currentVersion: string;
  phase: UpdatePhase;
  update: UpdateInfo | null;
  done: number;
  total: number | null;
  error: string | null;
}

const UPDATE_EVENT = "update";

export const browserUpdateStatus: UpdateStatus = {
  currentVersion: "dev",
  phase: "disabled",
  update: null,
  done: 0,
  total: null,
  error: null,
};

export function getUpdateStatus(): Promise<UpdateStatus> {
  if (!isTauriRuntime()) return Promise.resolve(browserUpdateStatus);
  return invoke<UpdateStatus>("get_update_status");
}

export async function onUpdateStatusChange(onChange: (status: UpdateStatus) => void): Promise<() => void> {
  if (!isTauriRuntime()) return () => {};
  return listen<UpdateStatus>(UPDATE_EVENT, (event) => onChange(event.payload));
}

export function checkForUpdates(): Promise<UpdateStatus> {
  return invoke<UpdateStatus>("check_for_updates");
}

export function downloadUpdate(): Promise<void> {
  return invoke("download_update");
}

export function cancelUpdateDownload(): Promise<void> {
  return invoke("cancel_update_download");
}

export function installUpdate(): Promise<void> {
  return invoke("install_update");
}
