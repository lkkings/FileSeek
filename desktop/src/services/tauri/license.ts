import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";

import { isTauriRuntime } from "./api";

/** Mirrors `license::status::Entitlement` in `src-tauri/src/license/status.rs`. */
export type EntitlementState = "licensed" | "unlicensed";

/** Why not licensed; mirrors `license::status::Reason`. */
export type UnlicensedReason = "none" | "invalid" | "revoked" | "offline_expired" | "no_device";

export interface Entitlement {
  state: EntitlementState;
  reason: UnlicensedReason | null;
  licenseId: string | null;
  planName: string | null;
  /** `null` with a license: it never expires. */
  validUntil: string | null;
  updatesUntil: string | null;
  /** Past the token's check-in time and offline: days left to connect. */
  offlineDaysLeft: number | null;
  clockAnomaly: boolean;
  purchaseUrl: string;
}

/** Mirrors `license::ActivationError`, serialized with a `kind` tag. */
export type ActivationError =
  | { kind: "empty_key" }
  | { kind: "not_found" }
  | { kind: "activation_limit"; current: number | null; max: number | null }
  | { kind: "expired" }
  | { kind: "suspended" }
  | { kind: "revoked" }
  | { kind: "canceled" }
  | { kind: "locked_out" }
  | { kind: "network" }
  | { kind: "bad_token" }
  | { kind: "server"; code: string }
  | { kind: "no_device" }
  | { kind: "not_activated" }
  | { kind: "io"; detail: string };

const ENTITLEMENT_EVENT = "entitlement";

/** Outside Tauri there is no license service; the browser preview counts as licensed. */
export const browserEntitlement: Entitlement = {
  state: "licensed",
  reason: null,
  licenseId: null,
  planName: null,
  validUntil: null,
  updatesUntil: null,
  offlineDaysLeft: null,
  clockAnomaly: false,
  purchaseUrl: "",
};

export function isActivationError(error: unknown): error is ActivationError {
  return typeof error === "object" && error !== null && typeof (error as ActivationError).kind === "string";
}

export function getEntitlement(): Promise<Entitlement> {
  if (!isTauriRuntime()) return Promise.resolve(browserEntitlement);
  return invoke<Entitlement>("get_entitlement");
}

export async function onEntitlementChange(onChange: (entitlement: Entitlement) => void): Promise<() => void> {
  if (!isTauriRuntime()) return () => {};
  return listen<Entitlement>(ENTITLEMENT_EVENT, (event) => onChange(event.payload));
}

export function activateLicense(key: string): Promise<Entitlement> {
  return invoke<Entitlement>("activate_license", { key });
}

export function deactivateLicense(): Promise<Entitlement> {
  return invoke<Entitlement>("deactivate_license");
}

/** Checks again now, online if the saved token says it is time. */
export function recheckLicense(): Promise<Entitlement> {
  return invoke<Entitlement>("recheck_license");
}

/** Opens the library folder in the system file manager. */
export function openLibraryFolder(): Promise<void> {
  if (!isTauriRuntime()) return Promise.resolve();
  return invoke("open_library_folder");
}
