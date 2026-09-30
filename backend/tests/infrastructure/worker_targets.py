"""供 spawn 子进程使用的测试 worker 入口。

spawn 按"模块路径 + 函数名"重新 import 目标函数，所以它们必须是可导入模块的顶层函数，
不能写在测试函数里。
"""

from __future__ import annotations

import os
import signal
import time
from multiprocessing.connection import Connection

from fileseek.shared.infrastructure.worker.loop import serve


def _handle(request: object, send_progress) -> object:
    if request == "sigkill":
        os.kill(os.getpid(), signal.SIGKILL)
    if request == "abort":
        os.abort()
    if request == "exit3":
        os._exit(3)
    if request == "raise":
        raise ValueError("boom")
    if isinstance(request, tuple) and request[0] == "sleep":
        time.sleep(float(request[1]))
    send_progress(("progress", request))
    return ("echo", request)


def echo_worker(conn: Connection, config: dict[str, object]) -> None:
    serve(conn, _handle, idle_timeout=float(config.get("idle_timeout", 0)))


def log_worker(conn: Connection, config: dict[str, object]) -> None:
    """按导入 worker 的方式初始化日志，打一行后退出。"""
    import logging

    from fileseek.features.tasks.infrastructure.worker import _bootstrap_worker

    _bootstrap_worker(config)
    logging.getLogger("fileseek.worker.test").info("hello-from-worker")
    conn.send("done")
