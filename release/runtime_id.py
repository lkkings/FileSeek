"""后端运行时包的标识。

`runtime_id` 只由依赖决定：`backend/uv.lock` 的内容、Python 版本和
python-build-standalone 的发布号。后端代码随应用分发，不参与计算，所以只改后端代码
的版本不会让用户重新下载运行时。

平台不参与计算：uv.lock 是跨平台的，同一个 `runtime_id` 在清单里按 target 各有一个包。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

RELEASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = RELEASE_DIR.parent
RUNTIME_CONFIG = RELEASE_DIR / "runtime.json"
UV_LOCK = REPO_ROOT / "backend" / "uv.lock"


def load_config(path: Path = RUNTIME_CONFIG) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def compute_runtime_id(lock_bytes: bytes, python_version: str, pbs_release: str) -> str:
    """`rt-` + sha256 的前 16 位十六进制。"""
    normalized = lock_bytes.replace(b"\r\n", b"\n")
    digest = hashlib.sha256()
    digest.update(normalized)
    digest.update(b"\0")
    digest.update(python_version.encode())
    digest.update(b"\0")
    digest.update(pbs_release.encode())
    return "rt-" + digest.hexdigest()[:16]


def current_runtime_id() -> str:
    config = load_config()
    return compute_runtime_id(UV_LOCK.read_bytes(), config["python_version"], config["pbs_release"])


if __name__ == "__main__":
    print(current_runtime_id())
