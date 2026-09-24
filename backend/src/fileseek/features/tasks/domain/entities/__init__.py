"""Tasks feature 领域实体和状态机。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from fileseek.features.tasks.domain.exceptions import InvalidTransitionError


class TaskStatus(str, Enum):
    """任务状态枚举。"""

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskStage(str, Enum):
    """任务处理阶段枚举。"""
    EXTRACTED = "extracted"
    ENCODED = "encoded"
    INDEXED = "indexed"

@dataclass
class TaskProgress:
    progress: int
    stage: TaskStage
    message: str | None = None


@dataclass
class Task:
    """任务领域实体（带状态机）。"""

    id: str
    source_path: str
    status: TaskStatus
    progress: int = 0
    stage: TaskStage | None = None

    error_message: str | None = None
    created_at: str = ""
    updated_at: str = ""


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
        self.progress = progress.progress

    def mark_completed(self) -> None:
        """标记任务完成（PROCESSING → COMPLETED）。"""
        if self.status != TaskStatus.PROCESSING:
            raise InvalidTransitionError(
                f"只能从 PROCESSING 状态标记完成，当前状态为 {self.status.value}"
            )
        self.progress = 100
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

    def retry(self) -> None:
        """重试失败的任务（FAILED → QUEUED）。"""
        if self.status != TaskStatus.FAILED:
            raise InvalidTransitionError(
                f"只能重试 FAILED 状态的任务，当前状态为 {self.status.value}"
            )
        self.status = TaskStatus.QUEUED
        self.error_message = None

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
