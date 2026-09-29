import { execFileSync } from "node:child_process";
import { cpSync, existsSync, mkdirSync, rmSync } from "node:fs";
import path from "node:path";

const isMacos = process.platform === "darwin";
if (!isMacos) {
  process.exit(0);
}

const root = path.resolve(import.meta.dirname, "..");
const source = path.join(root, "src-tauri", "macos", "FileSeekFinderSync");
const output = path.join(root, "src-tauri", "PlugIns", "FileSeekFinderSync.appex");
const contents = path.join(output, "Contents");
const executable = path.join(contents, "MacOS", "FileSeekFinderSync");
const entitlements = path.join(source, "FileSeekFinderSync.entitlements");

rmSync(output, { recursive: true, force: true });
mkdirSync(path.dirname(executable), { recursive: true });
cpSync(path.join(source, "Info.plist"), path.join(contents, "Info.plist"));
execFileSync(
  "xcrun",
  [
    "swiftc",
    "-framework",
    "AppKit",
    "-framework",
    "FinderSync",
    "-module-name",
    "FileSeekFinderSync",
    "-o",
    executable,
    path.join(source, "main.swift"),
    path.join(source, "FinderSync.swift"),
  ],
  { stdio: "inherit" },
);
execFileSync(
  "codesign",
  ["--force", "--sign", "-", "--entitlements", entitlements, output],
  { stdio: "inherit" },
);

if (!existsSync(executable)) {
  throw new Error("The Finder Sync extension executable was not created");
}
