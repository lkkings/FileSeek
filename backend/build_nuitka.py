"""把后端编译成桌面端随安装包发布的可执行文件。

    uv run python build_nuitka.py

产物在 `dist/fileseek-backend.dist/`，入口为 `fileseek-backend`（Windows 为 `.exe`）。
`desktop/scripts/stage-backend.mjs` 会调用本脚本并把整个目录拷进 Tauri 的资源目录。

用 `--standalone` 而不是 `--onefile`：导入和查询模型跑在 spawn 子进程里，每次启动子进程都会
重新执行入口，onefile 每次都要先解压一遍。

需要 C 编译器：macOS 上是 Xcode Command Line Tools 的 clang，Windows 上是 MSVC。
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENTRY = ROOT / "src" / "fileseek" / "__main__.py"
DIST = ROOT / "dist"
NAME = "fileseek-backend"
OUTPUT = DIST / f"{NAME}.dist"

# 产物目录总大小上限：首次实测值加 15% 余量。依赖变大导致超出时，先确认是不是带进了不该带的包。
# 2026-10 macOS arm64 实测 629 MB（大头：主程序 147、onnxruntime 70、cv2 40、grpc 19）。
SIZE_LIMIT_MB = 725


def nuitka_command() -> list[str]:
    command = [
        sys.executable,
        "-m",
        "nuitka",
        "--standalone",
        "--assume-yes-for-downloads",
        f"--output-dir={DIST}",
        f"--output-folder-name={NAME}.dist",
        f"--output-filename={NAME}",
        "--remove-output",
        # 路由、ORM 模型里有按名字加载的模块，整包包含比逐个追踪可靠。
        "--include-package=fileseek",
        # 下面几个包按字符串加载自己的实现，Nuitka 跟踪不到：chromadb 的 System 按
        # "chromadb.api.rust.RustBindingsAPI" 这类全名取类；uvicorn 按名字选 http/ws/lifespan
        # 协议；tortoise 把 sqlite:// 映射到 "tortoise.backends.sqlite" 再 import。
        "--include-package=chromadb",
        "--include-package=uvicorn",
        "--include-package=tortoise.backends.sqlite",
        # chromadb 的 SQL 迁移文件；rapidocr 自带的 .onnx 模型和 config.yaml。
        "--include-package-data=chromadb",
        "--include-package-data=rapidocr_onnxruntime",
        "--nofollow-import-to=pytest",
        "--nofollow-import-to=mypy",
        "--nofollow-import-to=ruff",
        "--nofollow-import-to=IPython",
    ]
    # Windows 保持控制台子系统：sidecar 用 CREATE_NO_WINDOW 启动，不会弹窗，而 stdout/stderr
    # 要重定向到 backend.log，GUI 子系统下这两个句柄可能是空的。
    command.append(str(ENTRY))
    return command


def directory_size(path: Path) -> int:
    return sum(entry.stat().st_size for entry in path.rglob("*") if entry.is_file())


def main() -> int:
    shutil.rmtree(OUTPUT, ignore_errors=True)
    result = subprocess.run(nuitka_command(), cwd=ROOT, check=False)  # noqa: S603
    if result.returncode != 0:
        print(f"nuitka failed with exit code {result.returncode}", file=sys.stderr)
        return result.returncode

    executable = OUTPUT / (f"{NAME}.exe" if sys.platform == "win32" else NAME)
    if not executable.is_file():
        print(f"expected executable not found: {executable}", file=sys.stderr)
        return 1

    size_mb = directory_size(OUTPUT) / (1024 * 1024)
    print(f"built {executable} ({size_mb:.0f} MB)")
    if SIZE_LIMIT_MB and size_mb > SIZE_LIMIT_MB:
        print(f"output is {size_mb:.0f} MB, over the {SIZE_LIMIT_MB} MB limit", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
