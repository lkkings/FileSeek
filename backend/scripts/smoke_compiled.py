"""启动编译后的后端，确认 `/health` 返回 ok。CI 在编译后跑它，本地也可以手动跑。

    uv run python scripts/smoke_compiled.py [path/to/fileseek-backend]

不传路径时用 `dist/fileseek-backend.dist/` 里的产物。配置目录指到一个临时目录，不碰真实的
连接文件和数据库。打印从启动到连接文件出现的耗时。
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
NAME = "fileseek-backend.exe" if sys.platform == "win32" else "fileseek-backend"
DEFAULT_EXE = ROOT / "dist" / "fileseek-backend.dist" / NAME
STARTUP_TIMEOUT = 120.0


def connection_file(home: Path) -> Path:
    """`config/paths.py` 按平台定位的连接文件，`home` 当作用户目录。"""
    if sys.platform == "win32":
        return home / "AppData" / "Roaming" / "FileSeek" / "connection.json"
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / "FileSeek" / "connection.json"
    return home / ".config" / "fileseek" / "connection.json"


def main() -> int:
    exe = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_EXE
    if not exe.is_file():
        print(f"compiled backend not found: {exe}", file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory(prefix="fileseek-smoke-") as tmp:
        home = Path(tmp)
        dropped = {"PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV", "PYTHONSTARTUP", "XDG_CONFIG_HOME"}
        env = {key: value for key, value in os.environ.items() if key not in dropped}
        env.update(
            HOME=str(home),
            USERPROFILE=str(home),
            APPDATA=str(home / "AppData" / "Roaming"),
            PYTHONUTF8="1",
        )
        log_path = home / "backend.log"
        conn = connection_file(home)
        started = time.monotonic()
        ok = False
        with log_path.open("wb") as log:
            process = subprocess.Popen(  # noqa: S603
                [str(exe)], env=env, stdout=log, stderr=subprocess.STDOUT
            )
            try:
                while not conn.is_file():
                    if process.poll() is not None:
                        break
                    if time.monotonic() - started > STARTUP_TIMEOUT:
                        break
                    time.sleep(0.1)
                elapsed = time.monotonic() - started
                if not conn.is_file():
                    print(f"no connection file after {elapsed:.1f}s", file=sys.stderr)
                    return 1
                info = json.loads(conn.read_text(encoding="utf-8"))
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
                # The backend's own output explains a failure; on success it is noise.
                if not ok:
                    sys.stderr.write(log_path.read_text(encoding="utf-8", errors="replace")[-4000:])


if __name__ == "__main__":
    raise SystemExit(main())
