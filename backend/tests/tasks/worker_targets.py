"""供 spawn 子进程使用的导入 worker 测试入口。

复用真实的 `make_task_request_handler` 和 `serve`，只把 handler 换成不加载模型的假实现，
这样测到的是真实的进程边界、消息协议和临时文件清理。
"""

from __future__ import annotations

import os
import signal
import time
from multiprocessing.connection import Connection

import numpy as np

from fileseek.features.tasks.application.compute import ChunkPayload, TaskResult, TaskSpec
from fileseek.features.tasks.application.handlers import FileHandlerRegistry
from fileseek.features.tasks.domain.entities import TaskStage
from fileseek.features.tasks.domain.ports import ProgressReporter
from fileseek.features.tasks.infrastructure.worker import make_task_request_handler
from fileseek.shared.domain.file_types import FileType
from fileseek.shared.infrastructure.worker.loop import serve


class _TextHandler:
    """按文件内容决定行为：`sigkill` 自杀、`sleep` 卡住、`fail` 抛异常，其余按行切块。"""

    def supports(self, file_type: FileType) -> bool:
        return file_type is FileType.TXT

    def compute(self, spec: TaskSpec, progress: ProgressReporter) -> TaskResult:
        path = spec.metadata["temp_path"]
        assert isinstance(path, str)
        text = open(path, encoding="utf-8").read()  # noqa: PTH123, SIM115
        progress.report(TaskStage.EXTRACTED, 1, 1)
        if text.startswith("sigkill"):
            os.kill(os.getpid(), signal.SIGKILL)
        if text.startswith("sleep"):
            time.sleep(60)
        if text.startswith("fail"):
            raise ValueError("无法解析")
        lines = [line for line in text.splitlines() if line]
        for index in range(len(lines)):
            progress.report(TaskStage.ENCODED, index + 1, len(lines))
        return TaskResult(
            chunks=tuple(ChunkPayload(metadata={"text": line}) for line in lines),
            vectors=np.ones((len(lines), 4), dtype=np.float32),
            tags=("note",),
            index_batch_size=2,
        )


def fake_task_worker(conn: Connection, config: dict[str, object]) -> None:
    registry = FileHandlerRegistry(handlers=[_TextHandler()])  # type: ignore[list-item]
    idle_timeout = float(config.get("idle_timeout", 0))
    serve(conn, make_task_request_handler(registry), idle_timeout=idle_timeout)
