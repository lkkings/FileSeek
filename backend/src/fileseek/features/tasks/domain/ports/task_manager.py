from __future__ import annotations

from typing import Protocol

from fileseek.features.tasks.domain.entities import Task


class TaskManager(Protocol):
    """任务管理能力。

    Tasks Feature 对外暴露的业务契约。
    """

    async def create(
        self,
        task: Task,
    ) -> Task:
        """创建并提交任务。"""
        ...

    async def get(
        self,
        task_id: str,
    ) -> Task | None:
        """获取任务。"""
        ...

    async def retry(
        self,
        task_id: str,
    ) -> Task:
        """重新执行任务。"""
        ...

    async def cancel(
        self,
        task_id: str,
    ) -> None:
        """取消任务。"""
        ...

    async def delete(
        self,
        task_id: str,
    ) -> None:
        """删除任务。"""
        ...
