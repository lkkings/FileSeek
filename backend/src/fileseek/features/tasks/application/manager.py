from __future__ import annotations

from datetime import datetime

from fileseek.features.tasks.domain.entities import Task, TaskStatus
from fileseek.features.tasks.domain.exceptions import InvalidTransitionError, TaskNotFoundError
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
    ) -> None:
        self.task_repo = task_repo

    async def create(
        self,
        task:Task
    ) -> Task:
        """创建任务并提交执行。"""
        now = datetime.now().isoformat()
        task.created_at = now,
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
        return Task


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
