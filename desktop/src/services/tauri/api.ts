import { invoke } from "@tauri-apps/api/core";

export interface TauriApiResponse {
  status: number;
  body: string;
}

export function isTauriRuntime() {
  const runtime = window as unknown as Record<string, unknown>;
  return runtime.__TAURI__ !== undefined || runtime.__TAURI_INTERNALS__ !== undefined;
}

export function requestApi(
  method: "GET" | "POST" | "PUT" | "PATCH" | "DELETE",
  path: string,
  body?: string,
) {
  return invoke<TauriApiResponse>("api_request", { method, path, body: body ?? null });
}
