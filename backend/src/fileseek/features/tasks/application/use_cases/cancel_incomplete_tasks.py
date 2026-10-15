from __future__ import annotations

from fileseek.features.tasks.application.dto import TaskBulkOperationDTO
from fileseek.features.tasks.domain.ports import TaskManager


class CancelIncompleteTasksUseCase:
    def __init__(self, task_manager: TaskManager) -> None:
        self.task_manager = task_manager

    async def execute(self) -> TaskBulkOperationDTO:
        count = await self.task_manager.cancel_incomplete()
        return TaskBulkOperationDTO(count=count)
