from __future__ import annotations

import logging
import queue
from pathlib import Path

from fileseek.features.library.domain.entities import File
from fileseek.features.tasks.application.handlers import (
    FileHandlerRegistry,
)
from fileseek.features.tasks.domain.ports import (
    ProgressReporter
)
from fileseek.features.tasks.domain.entities import (
    Task,
    TaskProgress,
)
from fileseek.infrastructure.vector_store import (
    VectorIndexPort
)
from fileseek.features.tasks.application.progress_reporter import QueueProgressReporter

logger = logging.getLogger(__name__)


class TaskProcessor:
    """任务内容处理器。

    负责协调：

        文件类型识别
            ↓
        Handler 查找
            ↓
        Handler.process()
            ↓
        Tags 持久化

    TaskProcessor 不负责具体文件类型的处理逻辑。
    """

    def __init__(
        self,
        handler_registry: FileHandlerRegistry,
        vector_index: VectorIndexPort
    ) -> None:
        self._handler_registry = handler_registry
        self._vector_index = vector_index

    def process(
        self,
        task: Task,
        progress_queue: queue.Queue[TaskProgress],
    ):
        """处理任务。"""

        logger.info(
            "开始处理任务: task_id=%s, path=%s",
            task.id,
            task.file.path,
        )

        # --------------------------------------------------
        # 1. 创建进度上报器
        # --------------------------------------------------

        progress = self._create_progress_reporter(
            progress_queue
        )

        # --------------------------------------------------
        # 2. 获取 Handler
        # --------------------------------------------------

        handler = self._handler_registry.get(
            task.file.file_type
        )

        logger.debug(
            "使用文件处理器: task_id=%s, handler=%s",
            task.id,
            type(handler).__name__,
        )


        # --------------------------------------------------
        # 3. Handler 完整处理
        # --------------------------------------------------
        temp_path = Path(task.metadata["temp_path"])
        handler.process(
            task,
            progress,
        )

        logger.info(
            "任务处理完成: task_id=%s",
            task.id,
        )

        # --------------------------------------------------
        # 4. 删除缓存文件
        # --------------------------------------------------

        temp_path.unlink(missing_ok=True)

    def _persist_tags(
        self,
        file_id: str,
        tags: list[str],
    ) -> None:
        """将文件标签写入向量索引。"""

        try:
            self._vector_index.update_file_tags(
                file_id,
                tags,
            )
        except Exception:
            logger.exception(
                "文件 tags 写入向量索引失败: file_id=%s",
                file_id,
            )

    @staticmethod
    def _create_progress_reporter(
        progress_queue: queue.Queue[TaskProgress],
    ) -> ProgressReporter:
        """创建进度上报器。

        没有进度队列时使用空实现，避免 Handler
        中出现大量 None 判断。
        """
        return QueueProgressReporter(
            progress_queue
        )