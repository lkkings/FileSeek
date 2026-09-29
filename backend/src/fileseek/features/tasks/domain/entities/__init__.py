"""Tasks feature 领域实体和状态机。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from fileseek.features.library.domain.entities import File, FileChunk
from fileseek.features.tasks.domain.exceptions import InvalidTransitionError


class TaskStatus(str, Enum):
    """任务状态枚举。"""

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskStage(str, Enum):
    """任务处理阶段枚举。"""
    EXTRACTED = "extracted"
    ENCODED = "encoded"
    CLASSIFY = "classify"
    INDEXED = "indexed"

@dataclass
class TaskProgress:
    stage: TaskStage
    completed_count: int
    total_count: int
    message: str | None = None

    def __post_init__(self) -> None:
        if self.completed_count < 0:
            raise ValueError("任务完成数量不能小于 0")
        if self.total_count <= 0:
            raise ValueError("任务总数量必须大于 0")
        if self.completed_count > self.total_count:
            raise ValueError("任务完成数量不能大于总数量")



@dataclass
class Task:
    id: str
    file: File
    metadata: dict[str, object] | None = None
    status: TaskStatus = TaskStatus.QUEUED
    completed_count: int | None = None
    total_count: int | None = None
    stage: TaskStage | None = None
    error_message: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def add_file_tags(self, tags: list[str]) -> None:
        self.file.add_tags(tags)

    def add_file_chunks(self, chunks: list[FileChunk]) -> None:
        self.file.add_chunks(chunks)


    def advance_stage(self, progress: TaskProgress) -> None:
        """推进任务阶段。

        `completed_stages` 只追加一次：同一阶段重复上报（或任务重试后再跑一遍）不该在
        列表里留下两条同名记录——前端按它渲染"已完成几步"。
        """
        if self.status != TaskStatus.PROCESSING:
            raise InvalidTransitionError(
                f"只能在 PROCESSING 状态推进阶段，当前状态为 {self.status.value}"
            )
        self.stage = progress.stage
        self.completed_count = progress.completed_count
        self.total_count = progress.total_count

    def mark_completed(self) -> None:
        """标记任务完成（PROCESSING → COMPLETED）。"""
        if self.status != TaskStatus.PROCESSING:
            raise InvalidTransitionError(
                f"只能从 PROCESSING 状态标记完成，当前状态为 {self.status.value}"
            )
        if self.total_count is not None:
            self.completed_count = self.total_count
        self.status = TaskStatus.COMPLETED
        self.error_message = None

    def mark_failed(self, error_message: str) -> None:
        """标记任务失败（PROCESSING → FAILED）。"""
        if self.status != TaskStatus.PROCESSING:
            raise InvalidTransitionError(
                f"只能从 PROCESSING 状态标记失败，当前状态为 {self.status.value}"
            )
        self.status = TaskStatus.FAILED
        self.error_message = error_message

    def mark_cancelled(self) -> None:
        """标记任务取消（PROCESSING → CANCELLED）。"""
        if self.status != TaskStatus.PROCESSING:
            raise InvalidTransitionError(
                f"只能取消 PROCESSING 状态的任务，当前状态为 {self.status.value}"
            )
        self.status = TaskStatus.CANCELLED
        self.error_message = "任务已终止"

    def retry(self) -> None:
        """重试失败或已终止的任务（FAILED/CANCELLED → QUEUED）。"""
        if self.status not in (TaskStatus.FAILED, TaskStatus.CANCELLED):
            raise InvalidTransitionError(
                f"只能重试 FAILED 或 CANCELLED 状态的任务，当前状态为 {self.status.value}"
            )
        self.status = TaskStatus.QUEUED
        self.error_message = None
        self.completed_count = None
        self.total_count = None

    def release(self) -> None:
        """把在飞任务放回队列（PROCESSING → QUEUED）。

        用于关闭超时和上次运行崩溃的遗留任务：它们不该判失败——文件没动过，
        已完成阶段也保留着，下次启动接着跑，而不是要用户重新添加一遍。
        """
        if self.status != TaskStatus.PROCESSING:
            raise InvalidTransitionError(
                f"只能放回 PROCESSING 状态的任务，当前状态为 {self.status.value}"
            )
        self.status = TaskStatus.QUEUED
        self.error_message = None
