import { openPath, revealItemInDir } from "@tauri-apps/plugin-opener";

import { isTauriRuntime } from "./api";

function normalizePath(path: string) {
  if (!path.startsWith("file://")) return path;
  return decodeURIComponent(path.replace(/^file:\/\//, ""));
}

export async function openPathInSystem(path: string) {
  if (!isTauriRuntime()) return false;
  await openPath(normalizePath(path));
  return true;
}

export async function revealPathInFolder(path: string) {
  if (!isTauriRuntime()) return false;
  await revealItemInDir(normalizePath(path));
  return true;
}
