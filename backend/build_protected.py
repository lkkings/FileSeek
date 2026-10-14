"""Build the protected backend package staged with the desktop app.

    uv run --extra dev python build_protected.py

The output is written to `dist/fileseek-backend-protected/`. It contains the obfuscated
`fileseek` package, PyArmor's runtime package, and non-Python package data from the source
tree. The package still needs the application dependencies from the downloaded Python
runtime; only application source is protected here.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PACKAGE = ROOT / "src" / "fileseek"
DIST = ROOT / "dist"
OUTPUT = DIST / "fileseek-backend-protected"
STAGING = DIST / "fileseek-backend-protected.tmp"


def pyarmor_command() -> list[str]:
    executable = shutil.which("pyarmor")
    if executable is None:
        raise RuntimeError("pyarmor is not on PATH; run with `uv run --extra dev`")
    return [executable]


def copy_package_data(source: Path, destination: Path) -> int:
    copied = 0
    for path in source.rglob("*"):
        if path.is_dir() or path.suffix == ".py" or "__pycache__" in path.parts:
            continue
        relative = path.relative_to(source)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        copied += 1
    return copied


def directory_size(path: Path) -> int:
    return sum(entry.stat().st_size for entry in path.rglob("*") if entry.is_file())


def validate(output: Path) -> None:
    entry = output / "fileseek" / "__main__.py"
    if not entry.is_file():
        raise RuntimeError(f"protected entry point is missing: {entry}")
    runtime = next(output.glob("pyarmor_runtime_*/pyarmor_runtime.*"), None)
    if runtime is None:
        raise RuntimeError(f"PyArmor runtime is missing from {output}")
    for path in output.rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="replace")
        if "__pyarmor__" not in text:
            raise RuntimeError(f"file is not PyArmor-protected: {path}")


def main() -> int:
    if not PACKAGE.is_dir():
        print(f"backend package not found: {PACKAGE}", file=sys.stderr)
        return 1

    shutil.rmtree(STAGING, ignore_errors=True)
    shutil.rmtree(OUTPUT, ignore_errors=True)
    DIST.mkdir(parents=True, exist_ok=True)

    command = [*pyarmor_command(), "gen", "-r", "-O", str(STAGING), str(PACKAGE)]
    result = subprocess.run(command, cwd=ROOT, check=False)  # noqa: S603
    if result.returncode != 0:
        print(f"pyarmor failed with exit code {result.returncode}", file=sys.stderr)
        shutil.rmtree(STAGING, ignore_errors=True)
        return result.returncode

    copied = copy_package_data(PACKAGE, STAGING / "fileseek")
    validate(STAGING)
    STAGING.rename(OUTPUT)

    print(f"built {OUTPUT} ({directory_size(OUTPUT) / 1_000_000:.1f} MB, {copied} data files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
