from __future__ import annotations

import logging
import queue

from fileseek.features.tasks.domain.ports import (
    ProgressReporter,
)
from fileseek.features.tasks.domain.entities import (
    TaskProgress,
    TaskStage,
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
    ) -> None:
        self._queue = progress_queue

    def report(
        self,
        progress: int,
        stage: TaskStage,
    ) -> None:
        try:
            self._queue.put(
                TaskProgress(
                    progress=max(0, min(100, progress)),
                    stage=stage,
                )
            )
        except Exception:
            logger.exception(
                "任务进度上报失败: stage=%s, progress=%s",
                stage.value,
                progress,
            )