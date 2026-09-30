"""供 spawn 子进程使用的假查询 worker：不加载模型，按查询文本决定行为。"""

from __future__ import annotations

import os
import signal
import time
from multiprocessing.connection import Connection

from fileseek.features.search.infrastructure.query_worker import QueryRequest
from fileseek.shared.infrastructure.worker.loop import serve


def _handle(request: object, send_progress) -> object:
    _ = send_progress
    assert isinstance(request, QueryRequest)
    text = request.texts[0]
    if text == "crash":
        os.kill(os.getpid(), signal.SIGKILL)
    if text == "hang":
        time.sleep(60)
    if text == "fail":
        raise ValueError("tokenizer broke")
    return [[float(len(t)), 1.0 if request.query else 0.0] for t in request.texts]


def fake_query_worker(conn: Connection, config: dict[str, object]) -> None:
    serve(conn, _handle, idle_timeout=float(config.get("idle_timeout", 0)))
