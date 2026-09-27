from __future__ import annotations

from typing import Protocol

from fileseek.features.tasks.domain.entities import TaskStage


class ProgressReporter(Protocol):
    """任务进度上报器。"""

    def report(
        self,
        progress: int,
        stage: TaskStage,
    ) -> None:
        """报告任务处理进度。"""
        ...