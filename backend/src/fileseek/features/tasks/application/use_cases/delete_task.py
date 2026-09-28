from __future__ import annotations

from fileseek.features.tasks.application.commands import DeleteTaskCommand
from fileseek.features.tasks.domain.ports import TaskManager


class DeleteTaskUseCase:
    def __init__(self, task_manager: TaskManager) -> None:
        self.task_manager = task_manager

    async def execute(self, command: DeleteTaskCommand) -> None:
        await self.task_manager.delete(command.task_id)
