"""Tasks feature 仓储端口定义。

Domain 层定义 Protocol 接口，Infrastructure 层提供具体实现。
"""

from __future__ import annotations

from typing import Protocol

from fileseek.features.tasks.domain.entities import Task, TaskStatus


class TaskRepository(Protocol):
    """任务仓储接口。"""

    async def get_by_id(self, task_id: str) -> Task | None: ...

    async def list_all(
        self,
        status: TaskStatus | None,
        page: int,
        page_size: int,
    ) -> tuple[list[Task], int]: ...

    async def save(self, task: Task) -> None: ...

    async def cancel(self, task_id: str) -> Task | None: ...

    async def delete(self, task_id: str) -> bool:
        """删除非处理中的任务，返回任务是否被删除。"""
        ...

    async def claim_next_queued(self) -> Task | None:
        """取出下一个待处理任务并标记状态，用于调度器轮询。"""
        ...
