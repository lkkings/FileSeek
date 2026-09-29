from __future__ import annotations

from fileseek.features.tasks.application.commands import CancelTaskCommand
from fileseek.features.tasks.application.dto import TaskDTO
from fileseek.features.tasks.application.mappers import task_to_dto
from fileseek.features.tasks.domain.ports import TaskManager


class CancelTaskUseCase:
    def __init__(self, task_manager: TaskManager) -> None:
        self.task_manager = task_manager

    async def execute(self, command: CancelTaskCommand) -> TaskDTO:
        task = await self.task_manager.cancel(command.task_id)
        return task_to_dto(task)
