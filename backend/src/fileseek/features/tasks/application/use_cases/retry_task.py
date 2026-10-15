from fileseek.features.tasks.application.commands import RetryTaskCommand
from fileseek.features.tasks.application.dto import TaskDTO
from fileseek.features.tasks.application.mappers import task_to_dto
from fileseek.features.tasks.domain.ports import TaskManager


class RetryTaskUseCase:
    def __init__(self, task_manager: TaskManager) -> None:
        self.task_manager = task_manager

    async def execute(self, command: RetryTaskCommand) -> TaskDTO:
        task_id = command.task_id
        task = await self.task_manager.retry(task_id)
        return task_to_dto(task)
