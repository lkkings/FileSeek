// Protects the backend with PyArmor (`backend/build_protected.py`) and copies the result
// into `src-tauri/resources/backend/` so Tauri bundles it as a resource. Release builds
// start it with the downloaded Python interpreter (see `src-tauri/src/readiness.rs`).
import { spawnSync } from "node:child_process";
import { existsSync, readdirSync, readFileSync, rmSync, cpSync } from "node:fs";
import path from "node:path";

const root = path.resolve(import.meta.dirname, "..");
const backend = path.resolve(root, "..", "backend");
const protectedDir = path.join(backend, "dist", "fileseek-backend-protected");
const output = path.join(root, "src-tauri", "resources", "backend");

// `--extra dev`: PyArmor is a development dependency, absent from a fresh checkout's
// production environment.
const build = spawnSync("uv", ["run", "--directory", backend, "--extra", "dev", "python", "build_protected.py"], {
  stdio: "inherit",
  shell: process.platform === "win32",
});
if (build.error) {
  console.error(`could not run uv to protect the backend: ${build.error.message}`);
  process.exit(1);
}
if (build.status !== 0) {
  console.error(`protecting the backend failed (exit ${build.status}); see the PyArmor output above`);
  process.exit(build.status ?? 1);
}
if (!existsSync(path.join(protectedDir, "fileseek", "__main__.py"))) {
  console.error(`protected backend entry point is missing at ${protectedDir}`);
  process.exit(1);
}
if (readdirSync(protectedDir, { recursive: true }).filter((entry) => String(entry).endsWith(".py")).length === 0) {
  console.error(`protected backend contains no Python modules at ${protectedDir}`);
  process.exit(1);
}

const unprotected = readdirSync(protectedDir, { recursive: true })
  .filter((entry) => String(entry).endsWith(".py"))
  .find((entry) => {
    const file = path.join(protectedDir, String(entry));
    return !readFileSync(file, "utf8").includes("__pyarmor__");
  });
if (unprotected) {
  console.error(`protected backend contains plaintext Python source: ${unprotected}`);
  process.exit(1);
}

rmSync(output, { recursive: true, force: true });
cpSync(protectedDir, output, { recursive: true, verbatimSymlinks: true });
console.log(`staged protected backend into ${output}`);
