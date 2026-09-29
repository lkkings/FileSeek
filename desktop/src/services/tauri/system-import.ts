import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";

import { isTauriRuntime } from "./api";

export const systemImportEventName = "system-import-request";

export interface SystemImportRequest {
  paths: string[];
  errors: string[];
}

export function parseSystemImportRequest(payload: unknown): SystemImportRequest | null {
  if (typeof payload !== "object" || payload === null) {
    return null;
  }

  const { paths, errors } = payload as Record<string, unknown>;
  if (!Array.isArray(paths) || !Array.isArray(errors)) {
    return null;
  }
  if (paths.some((path) => typeof path !== "string" || path.trim() === "")) {
    return null;
  }
  if (errors.some((error) => typeof error !== "string")) {
    return null;
  }
  if (paths.length === 0 && errors.length === 0) {
    return null;
  }

  return { paths, errors };
}

export async function listenSystemImportRequest(
  onRequest: (request: SystemImportRequest) => void,
): Promise<() => void> {
  if (!isTauriRuntime()) {
    return () => undefined;
  }

  const unlisten = await listen<unknown>(systemImportEventName, (event) => {
    const request = parseSystemImportRequest(event.payload);
    if (request) {
      onRequest(request);
    }
  });

  const pending = parseSystemImportRequest(
    await invoke<unknown>("take_pending_system_import"),
  );
  if (pending) {
    onRequest(pending);
  }

  return unlisten;
}
