from __future__ import annotations

import logging
from collections.abc import Callable

from fileseek.features.tasks.domain.entities import (
    TaskProgress,
    TaskStage,
)
from fileseek.features.tasks.domain.ports import (
    ProgressReporter,
)

logger = logging.getLogger(__name__)


class CallbackProgressReporter(ProgressReporter):
    """把进度交给一个回调的上报器。

    子进程里回调是"经 Pipe 发回服务进程"，服务进程里（`persist` 阶段）是"推进任务并记下来"。

    进度属于派生信息，投递失败不能影响核心任务处理；但计数不合法是调用方的 bug，
    照常抛出。

    终止任务不再靠这里检查：子进程拿不到服务进程的取消登记，终止由调度器直接结束
    子进程完成，即使计算正卡在一次长推理里也能立刻生效。
    """

    def __init__(self, sink: Callable[[TaskProgress], None]) -> None:
        self._sink = sink

    def report(
        self,
        stage: TaskStage,
        completed_count: int,
        total_count: int,
    ) -> None:
        task_progress = TaskProgress(
            stage=stage,
            completed_count=completed_count,
            total_count=total_count,
        )
        try:
            self._sink(task_progress)
        except Exception:
            logger.exception(
                "任务进度上报失败: stage=%s",
                stage.value,
            )
