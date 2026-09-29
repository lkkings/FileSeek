from __future__ import annotations

import logging
import queue

from fileseek.features.tasks.application.cancellation import (
    TaskCancellationRegistry,
)
from fileseek.features.tasks.domain.entities import (
    TaskProgress,
    TaskStage,
)
from fileseek.features.tasks.domain.exceptions import TaskCancelledError
from fileseek.features.tasks.domain.ports import (
    ProgressReporter,
)

logger = logging.getLogger(__name__)


class QueueProgressReporter(ProgressReporter):
    """基于 Queue 的进度上报器。

    进度属于派生信息。
    上报失败不能影响核心任务处理。
    """

    def __init__(
        self,
        progress_queue: queue.Queue[TaskProgress],
        cancellation_registry: TaskCancellationRegistry | None = None,
        task_id: str | None = None,
    ) -> None:
        self._queue = progress_queue
        self._cancellation_registry = cancellation_registry
        self._task_id = task_id

    def report(
        self,
        stage: TaskStage,
        completed_count: int,
        total_count: int,
    ) -> None:
        if (
            self._cancellation_registry is not None
            and self._task_id is not None
            and self._cancellation_registry.is_cancelled(self._task_id)
        ):
            raise TaskCancelledError(f"任务 {self._task_id} 已终止")

        task_progress = TaskProgress(
            stage=stage,
            completed_count=completed_count,
            total_count=total_count,
        )
        try:
            self._queue.put(task_progress)
        except Exception:
            logger.exception(
                "任务进度上报失败: stage=%s",
                stage.value,
            )
