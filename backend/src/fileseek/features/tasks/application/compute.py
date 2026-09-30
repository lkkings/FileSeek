"""导入计算的跨进程数据契约。

计算（解析、向量化、OCR、分类）跑在模型子进程里，写入（向量库、文件块登记）留在服务进程。
两边之间只传这里定义的纯数据：`TaskSpec` 进，`TaskResult` 出。它们要能被 pickle，所以
不引用 `Task`、`File` 这些带行为的实体，也不含任何服务对象。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import numpy as np

from fileseek.shared.domain.file_types import FileType


@dataclass(frozen=True)
class TaskSpec:
    """交给子进程的一次计算请求。"""

    task_id: str
    file_id: str
    file_type: FileType
    file_path: str
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ChunkPayload:
    """一个待索引的块。它在结果里的下标就是向量 id 的后缀（`{file_id}_{index}`）。"""

    metadata: dict[str, object]


@dataclass(frozen=True)
class TaskResult:
    """一次计算的结果。`vectors` 与 `chunks` 一一对应。

    `index_batch_size` 是写入向量库时的分批大小：沿用各 handler 原来的批次，这样前端看到的
    INDEXED 进度粒度和改造前一样。
    """

    chunks: tuple[ChunkPayload, ...] = ()
    vectors: np.ndarray = field(default_factory=lambda: np.zeros((0, 0), dtype=np.float32))
    tags: tuple[str, ...] = ()
    index_batch_size: int = 1

    def __post_init__(self) -> None:
        if len(self.chunks) != len(self.vectors):
            raise ValueError(
                f"chunks 与 vectors 数量不一致: {len(self.chunks)} != {len(self.vectors)}"
            )
        if self.index_batch_size <= 0:
            raise ValueError("index_batch_size 必须大于 0")

    @classmethod
    def empty(cls) -> TaskResult:
        return cls()


def as_vector_array(vectors: list[list[float]]) -> np.ndarray:
    """把 embedding 列表收成 float32 矩阵：跨进程传输体积只有 list 的约四分之一。"""
    if not vectors:
        return np.zeros((0, 0), dtype=np.float32)
    return np.asarray(vectors, dtype=np.float32)


class TaskComputeFailedError(RuntimeError):
    """子进程里的计算抛了 Python 异常（进程本身仍健康）。"""

    def __init__(self, message: str, error_type: str = "") -> None:
        super().__init__(message)
        self.error_type = error_type


class TaskComputePort(Protocol):
    """调度器视角的计算进程。

    `poll` 非阻塞地返回下一个事件：进度（`TaskProgress`）、结果（`TaskResult`）、
    或一个异常实例（`TaskComputeFailedError` / 进程崩溃）。没有事件时返回 None。
    """

    def in_cooldown(self) -> bool: ...

    def submit(self, spec: TaskSpec) -> None: ...

    def poll(self) -> object | None: ...

    def terminate(self) -> None: ...

    def shutdown(self) -> None: ...
