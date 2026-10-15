from __future__ import annotations

import asyncio
import time
from datetime import datetime

from fileseek.features.tasks.application.cancellation import (
    TaskCancellationRegistry,
)
from fileseek.features.tasks.domain.entities import Task, TaskStatus
from fileseek.features.tasks.domain.exceptions import (
    InvalidTransitionError,
    TaskCancellationPendingError,
    TaskNotFoundError,
)
from fileseek.features.tasks.domain.ports import TaskManager
from fileseek.features.tasks.domain.repositories import (
    TaskRepository,
)


class DefaultTaskManager(TaskManager):
    """任务管理器默认实现。

    负责：

    - 创建任务
    - 查询任务
    - 重试任务
    - 取消任务
    - 删除任务
    - 将任务提交给调度器

    不负责：

    - 文件内容解析
    - OCR
    - Embedding
    - 向量索引
    - 线程池 / 进程池具体实现
    """

    def __init__(
        self,
        task_repo: TaskRepository,
        cancellation_registry: TaskCancellationRegistry | None = None,
    ) -> None:
        self.task_repo = task_repo
        self.cancellation_registry = cancellation_registry

    CANCELLATION_CLEANUP_TIMEOUT_SECONDS = 5.0

    async def _wait_for_cancellation_cleanup(self) -> None:
        if self.cancellation_registry is None:
            return

        deadline = time.monotonic() + self.CANCELLATION_CLEANUP_TIMEOUT_SECONDS
        while self.cancellation_registry.pending_ids():
            if time.monotonic() >= deadline:
                raise TaskCancellationPendingError("任务终止尚未完成，不能继续")
            await asyncio.sleep(0.01)

    async def create(self, task: Task) -> Task:
        """创建任务并提交执行。"""
        now = datetime.now()
        task.created_at = now
        task.updated_at = now
        task.status = TaskStatus.QUEUED
        await self.task_repo.save(task)
        return task

    async def get(
        self,
        task_id: str,
    ) -> Task:
        """获取任务。"""
        task = await self.task_repo.get_by_id(task_id)

        if task is None:
            raise TaskNotFoundError(f"任务 {task_id} 不存在")
        return task

    async def retry(
        self,
        task_id: str,
    ) -> Task:
        """重新提交任务。

        状态转换由 Task 实体负责，Manager 只负责：
            查询 → 状态转换 → 持久化 → 提交调度器
        """
        task = await self.task_repo.get_by_id(task_id)

        if task is None:
            raise TaskNotFoundError(f"任务 {task_id} 不存在")
        try:
            task.retry()
        except InvalidTransitionError as exc:
            raise InvalidTransitionError(f"无法重试任务 {task_id}：{exc}") from exc

        task.updated_at = datetime.now()

        await self.task_repo.save(task)
        return task

    async def cancel(
        self,
        task_id: str,
    ) -> Task:
        """终止处理中的任务。"""
        task = await self.task_repo.get_by_id(task_id)

        if task is None:
            raise TaskNotFoundError(f"任务 {task_id} 不存在")

        if task.status is not TaskStatus.PROCESSING:
            raise InvalidTransitionError(f"任务 {task_id} 不在处理中，不能终止")

        if self.cancellation_registry is not None:
            self.cancellation_registry.request(task_id)

        cancelled_task = await self.task_repo.cancel(task_id)
        if cancelled_task is None:
            if self.cancellation_registry is not None:
                self.cancellation_registry.clear(task_id)
            current = await self.task_repo.get_by_id(task_id)
            if current is None:
                raise TaskNotFoundError(f"任务 {task_id} 不存在")
            raise InvalidTransitionError(f"任务 {task_id} 状态已变化，不能终止")

        return cancelled_task

    async def delete(
        self,
        task_id: str,
    ) -> None:
        """删除任务。

        处理中的任务不能删除：调度线程稍后会继续保存任务进度，
        无条件删除会让任务通过 update_or_create 重新出现。
        """
        task = await self.task_repo.get_by_id(task_id)

        if task is None:
            raise TaskNotFoundError(f"任务 {task_id} 不存在")

        if task.status is TaskStatus.PROCESSING:
            raise InvalidTransitionError(f"任务 {task_id} 正在处理，不能移除")

        deleted = await self.task_repo.delete(task_id)

        if not deleted:
            current = await self.task_repo.get_by_id(task_id)
            if current is None:
                raise TaskNotFoundError(f"任务 {task_id} 不存在")
            raise InvalidTransitionError(f"任务 {task_id} 状态已变化，不能移除")

    async def cancel_incomplete(self) -> int:
        """批量取消 queued/processing 任务，调度器生命周期保持不变。"""
        cancelled_count, processing_ids = await self.task_repo.cancel_incomplete()

        if self.cancellation_registry is not None:
            for task_id in processing_ids:
                self.cancellation_registry.request(task_id)

        return cancelled_count

    async def continue_cancelled(self) -> int:
        """等待取消收尾完成后，批量恢复 cancelled 任务。"""
        await self._wait_for_cancellation_cleanup()
        return await self.task_repo.continue_cancelled()

    async def delete_completed(self) -> int:
        """批量删除 completed 任务，保留关联文件。"""
        return await self.task_repo.delete_completed()
