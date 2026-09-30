"""日志配置。

日志同时写到 stderr 和配置目录下的文件。stderr 那一路不是冗余：桌面端启动后端
失败时，读的就是子进程 stderr 的尾部（`sidecar.rs::read_stderr_tail`），日志只
进文件的话那条错误信息会是空的。
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
# 模型子进程和服务进程写同一个日志文件，行首带上进程名才分得清是谁打的。
_WORKER_FORMAT = "%(asctime)s %(levelname)-8s [%(processName)s] %(name)s: %(message)s"


def configure_logging(
    level: str = "INFO",
    log_file: Path | None = None,
    *,
    worker: bool = False,
) -> None:
    """配置根 logger。

    Args:
        level: 日志级别名（INFO / DEBUG / ...）
        log_file: 日志文件路径，None 表示只写 stderr
        worker: 是否为模型子进程，是则在每行带上进程名
    """
    root = logging.getLogger()
    root.setLevel(level.upper())

    # 清掉已有 handler：uvicorn 和重复调用都会装上自己的一套，不清就会重复打印。
    for handler in list(root.handlers):
        root.removeHandler(handler)

    formatter = logging.Formatter(_WORKER_FORMAT if worker else _FORMAT)

    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setFormatter(formatter)
    root.addHandler(stream_handler)

    if log_file is not None:
        try:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setFormatter(formatter)
            root.addHandler(file_handler)
        except OSError as exc:
            # 目录不可写不该让服务起不来——stderr 那一路还在。
            root.warning("日志文件 %s 无法写入，仅输出到 stderr: %s", log_file, exc)
