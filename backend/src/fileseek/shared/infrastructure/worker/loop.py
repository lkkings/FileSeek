"""子进程侧的主循环。

两个 worker（导入、查询）的循环结构一样：等请求 → 处理 → 回结果，空闲超时就自己退出。
差别只在"怎么处理一个请求"，所以这里只收一个 `handle(request, send_progress)` 回调。
"""

from __future__ import annotations

import logging
import traceback
from collections.abc import Callable
from multiprocessing.connection import Connection

from fileseek.shared.infrastructure.worker.protocol import (
    ErrorMessage,
    IdleExitMessage,
    ProgressMessage,
    ResultMessage,
    ShutdownMessage,
)

logger = logging.getLogger(__name__)

RequestHandler = Callable[[object, Callable[[object], None]], object]


def serve(
    conn: Connection,
    handle: RequestHandler,
    *,
    idle_timeout: float,
) -> None:
    """在子进程里跑请求循环，直到空闲超时、收到 shutdown 或父进程断开。

    Args:
        conn: 与服务进程相连的 Pipe 端点
        handle: 处理一个请求并返回结果；可以通过第二个参数随时发送进度
        idle_timeout: 连续多少秒没有请求就退出；0 表示永不因空闲退出

    请求处理中抛出的 Python 异常以 `ErrorMessage` 回传，进程继续服务下一个请求：
    一个文件解析失败不该让模型重新加载一遍。
    """

    def send_progress(payload: object) -> None:
        conn.send(ProgressMessage(payload))

    timeout = idle_timeout if idle_timeout > 0 else None
    while True:
        try:
            if not conn.poll(timeout):
                logger.info("模型进程空闲 %.0fs，正常退出", idle_timeout)
                conn.send(IdleExitMessage())
                return
            request = conn.recv()
        except (EOFError, OSError):
            # 父进程已经不在了（崩溃或被强杀）：没有人会再来取结果，直接退出。
            return

        if isinstance(request, ShutdownMessage):
            return

        try:
            result = handle(request, send_progress)
        except Exception as exc:  # noqa: BLE001 - 回传给服务进程决定怎么处理
            conn.send(
                ErrorMessage(
                    str(exc) or type(exc).__name__,
                    traceback.format_exc(),
                    type(exc).__name__,
                )
            )
        else:
            conn.send(ResultMessage(result))
