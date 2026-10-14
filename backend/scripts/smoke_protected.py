"""Start a protected backend package with a Python runtime and check `/health`.

    uv run python scripts/smoke_protected.py [python] [path/to/protected/package]

With no arguments the script uses the current interpreter and
`dist/fileseek-backend-protected/`. The configuration directory points at a temporary
directory so the smoke run does not touch the real connection file or database.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACKAGE = ROOT / "dist" / "fileseek-backend-protected"
STARTUP_TIMEOUT = 120.0


def connection_file(home: Path) -> Path:
    if sys.platform == "win32":
        return home / "AppData" / "Roaming" / "FileSeek" / "connection.json"
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / "FileSeek" / "connection.json"
    return home / ".config" / "fileseek" / "connection.json"


def main() -> int:
    arguments = sys.argv[1:]
    python = Path(arguments[0]) if arguments else Path(sys.executable)
    package = Path(arguments[1]) if len(arguments) > 1 else DEFAULT_PACKAGE
    if not python.is_file():
        print(f"Python interpreter not found: {python}", file=sys.stderr)
        return 1
    if not (package / "fileseek" / "__main__.py").is_file():
        print(f"protected backend not found: {package}", file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory(prefix="fileseek-smoke-") as tmp:
        home = Path(tmp)
        dropped = {"PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV", "PYTHONSTARTUP", "XDG_CONFIG_HOME"}
        env = {key: value for key, value in os.environ.items() if key not in dropped}
        env.update(
            HOME=str(home),
            USERPROFILE=str(home),
            APPDATA=str(home / "AppData" / "Roaming"),
            LIB_ROOT=str(home / "FileSeekLibrary"),
            PYTHONUTF8="1",
            PYTHONPATH=str(package),
        )
        log_path = home / "backend.log"
        connection = connection_file(home)
        started = time.monotonic()
        ok = False
        with log_path.open("wb") as log:
            process = subprocess.Popen(  # noqa: S603
                [str(python), "-m", "fileseek"],
                cwd=ROOT,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            try:
                while not connection.is_file():
                    if process.poll() is not None:
                        break
                    if time.monotonic() - started > STARTUP_TIMEOUT:
                        break
                    time.sleep(0.1)
                elapsed = time.monotonic() - started
                if not connection.is_file():
                    print(f"no connection file after {elapsed:.1f}s", file=sys.stderr)
                    return 1
                info = json.loads(connection.read_text(encoding="utf-8"))
                request = urllib.request.Request(
                    f"http://127.0.0.1:{info['port']}/health",
                    headers={"X-FileSeek-Token": info["token"]},
                )
                with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310
                    body = json.loads(response.read())
                if body.get("data", {}).get("status") != "ok":
                    print(f"unexpected /health response: {body}", file=sys.stderr)
                    return 1
                print(f"ok: /health answered, connection file after {elapsed:.1f}s")
                ok = True
                return 0
            finally:
                process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                if not ok:
                    sys.stderr.write(log_path.read_text(encoding="utf-8", errors="replace")[-4000:])


if __name__ == "__main__":
    raise SystemExit(main())
