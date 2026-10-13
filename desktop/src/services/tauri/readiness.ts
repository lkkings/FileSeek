import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";

import { isTauriRuntime } from "./api";

/** Mirrors `readiness::State` in `src-tauri/src/readiness.rs`. */
export type ReadinessState =
  | "license_check"
  /** No valid license: only the activation screen. */
  | "activation"
  | "checking"
  | "space_check"
  | "downloading"
  | "verifying"
  | "installing"
  | "starting"
  | "ready"
  | "failed"
  | "repair_needed";

export type ReadinessErrorKind =
  | "network"
  | "integrity"
  | "disk_space"
  | "unwritable"
  | "install"
  | "backend"
  | "unsupported";

export interface Readiness {
  state: ReadinessState;
  done: number;
  total: number;
  bytesPerSecond: number;
  failedStep: ReadinessState | null;
  errorKind: ReadinessErrorKind | null;
  error: string | null;
  space: { path: string; required: number; available: number } | null;
  unwritablePath: string | null;
  logPath: string | null;
}

const READINESS_EVENT = "readiness";

/** Outside Tauri (`pnpm dev` in a browser) there is no supervisor; the backend is whatever is running. */
export const browserReadiness: Readiness = {
  state: "ready",
  done: 0,
  total: 0,
  bytesPerSecond: 0,
  failedStep: null,
  errorKind: null,
  error: null,
  space: null,
  unwritablePath: null,
  logPath: null,
};

export function getReadiness(): Promise<Readiness> {
  if (!isTauriRuntime()) return Promise.resolve(browserReadiness);
  return invoke<Readiness>("get_readiness");
}

/** Calls `onChange` with every readiness update; resolves to the unsubscribe function. */
export async function onReadinessChange(onChange: (readiness: Readiness) => void): Promise<() => void> {
  if (!isTauriRuntime()) return () => {};
  return listen<Readiness>(READINESS_EVENT, (event) => onChange(event.payload));
}

export function retryReadiness(): Promise<void> {
  if (!isTauriRuntime()) return Promise.resolve();
  return invoke("retry_readiness");
}

export function repairRuntime(): Promise<void> {
  if (!isTauriRuntime()) return Promise.resolve();
  return invoke("repair_runtime");
}

export function hideToTray(): Promise<void> {
  if (!isTauriRuntime()) return Promise.resolve();
  return invoke("hide_to_tray");
}
