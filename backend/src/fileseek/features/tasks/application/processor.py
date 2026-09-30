from __future__ import annotations

import logging

from fileseek.features.library.domain.entities import FileChunk
from fileseek.features.tasks.application.compute import TaskResult, TaskSpec
from fileseek.features.tasks.domain.entities import (
    Task,
    TaskStage,
)
from fileseek.features.tasks.domain.ports import ProgressReporter
from fileseek.infrastructure.vector_store import VectorIndexPort

logger = logging.getLogger(__name__)


class TaskProcessor:
    """任务的服务进程侧：把计算结果写进向量库和文件实体。

    计算（抽取、编码、分类）在模型子进程里由 Handler 完成，这里只负责：

        TaskSpec 构建
            ↓
        （子进程计算）
            ↓
        向量写入 + 文件块 / 标签登记
            ↓
        终止时回收已写入的向量

    向量库只由服务进程写：Chroma `PersistentClient` 不支持多进程并发写，回收站删除又
    恰好在服务进程里写它。
    """

    def __init__(
        self,
        vector_index: VectorIndexPort,
    ) -> None:
        self._vector_index = vector_index

    @staticmethod
    def build_spec(task: Task) -> TaskSpec:
        """从任务构造交给子进程的计算请求。"""
        return TaskSpec(
            task_id=task.id,
            file_id=task.file.id,
            file_type=task.file.file_type,
            file_path=task.file.path,
            metadata=dict(task.metadata or {}),
        )

    def persist(
        self,
        task: Task,
        result: TaskResult,
        progress: ProgressReporter,
    ) -> None:
        """按批写入向量并登记文件块，最后登记标签。

        向量 id 规则是 `{file_id}_{index}`：检索结果按它回查文件块，`cleanup` 也按它删除。
        """
        if result.tags:
            task.add_file_tags(list(result.tags))

        total = len(result.chunks)
        if total == 0:
            logger.info("任务没有可索引内容: task_id=%s", task.id)
            return

        batch_size = result.index_batch_size
        progress.report(
            TaskStage.INDEXED,
            completed_count=0,
            total_count=total,
        )
        for start in range(0, total, batch_size):
            payloads = result.chunks[start : start + batch_size]
            ids = [
                f"{task.file.id}_{start + offset}"
                for offset in range(len(payloads))
            ]
            vectors = result.vectors[start : start + batch_size].tolist()
            self._vector_index.add_batch(ids, vectors)
            task.add_file_chunks(
                [
                    FileChunk(
                        id=chunk_id,
                        file_id=task.file.id,
                        metadata=payload.metadata,
                    )
                    for chunk_id, payload in zip(ids, payloads, strict=True)
                ]
            )
            progress.report(
                TaskStage.INDEXED,
                completed_count=start + len(payloads),
                total_count=total,
            )
        progress.report(
            TaskStage.INDEXED,
            completed_count=total,
            total_count=total,
        )

    def cleanup(self, task: Task) -> None:
        """删除终止前已写入的部分向量。"""
        ids = [chunk.id for chunk in task.file.chunks]
        if ids:
            self._vector_index.delete_batch(ids)
