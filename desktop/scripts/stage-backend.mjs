// Copies the backend's Python source into `src-tauri/resources/backend/` so Tauri bundles
// it as a resource. Production builds run it on the downloaded runtime with
// `PYTHONPATH=<resources>/backend` (see `src-tauri/src/sidecar.rs`).
//
// Only `.py` files are copied: `__pycache__` from a dev checkout would ship bytecode for
// whatever Python the developer happens to run, and the backend has no data files.
import { cpSync, existsSync, rmSync, statSync } from "node:fs";
import path from "node:path";

const root = path.resolve(import.meta.dirname, "..");
const source = path.resolve(root, "..", "backend", "src", "fileseek");
const output = path.join(root, "src-tauri", "resources", "backend", "fileseek");

if (!existsSync(source)) {
  console.error(`backend source not found at ${source}`);
  process.exit(1);
}

rmSync(path.dirname(output), { recursive: true, force: true });
cpSync(source, output, {
  recursive: true,
  filter: (entry) => statSync(entry).isDirectory() ? path.basename(entry) !== "__pycache__" : entry.endsWith(".py"),
});
console.log(`staged backend into ${output}`);
