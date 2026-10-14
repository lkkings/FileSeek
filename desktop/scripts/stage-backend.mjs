// Compiles the backend with Nuitka (`backend/build_nuitka.py`) and copies the result into
// `src-tauri/resources/backend/` so Tauri bundles it as a resource. Release builds run
// `<resources>/backend/fileseek-backend[.exe]` directly (see `src-tauri/src/readiness.rs`).
//
// The compiled directory holds no `.py` source; the whole directory is copied because the
// executable loads its extension modules and data files from next to itself.
import { spawnSync } from "node:child_process";
import { chmodSync, cpSync, existsSync, rmSync } from "node:fs";
import path from "node:path";

const root = path.resolve(import.meta.dirname, "..");
const backend = path.resolve(root, "..", "backend");
const compiled = path.join(backend, "dist", "fileseek-backend.dist");
const output = path.join(root, "src-tauri", "resources", "backend");
const exe = process.platform === "win32" ? "fileseek-backend.exe" : "fileseek-backend";

// `--extra dev`: nuitka is a dev dependency, absent from a fresh checkout's environment.
const build = spawnSync("uv", ["run", "--directory", backend, "--extra", "dev", "python", "build_nuitka.py"], {
  stdio: "inherit",
  shell: process.platform === "win32",
});
if (build.error) {
  console.error(`could not run uv to compile the backend: ${build.error.message}`);
  process.exit(1);
}
if (build.status !== 0) {
  console.error(`compiling the backend failed (exit ${build.status}); see the Nuitka output above`);
  process.exit(build.status ?? 1);
}
if (!existsSync(path.join(compiled, exe))) {
  console.error(`compiled backend not found at ${path.join(compiled, exe)}`);
  process.exit(1);
}

rmSync(output, { recursive: true, force: true });
cpSync(compiled, output, { recursive: true, verbatimSymlinks: true });
if (process.platform !== "win32") {
  chmodSync(path.join(output, exe), 0o755);
}
console.log(`staged compiled backend into ${output}`);
