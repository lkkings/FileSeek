from fileseek.features.tasks.application.dto import TaskDTO
from fileseek.features.tasks.application.mappers import task_to_dto
from fileseek.features.tasks.application.queries import GetTaskQuery
from fileseek.features.tasks.domain.exceptions import TaskNotFoundError
from fileseek.features.tasks.domain.ports import TaskManager


class GetTaskUseCase:
    def __init__(self, task_manager: TaskManager) -> None:
        self.task_manager = task_manager

    async def execute(self, query: GetTaskQuery) -> TaskDTO:
        task = self.task_manager.get(query.task_id)
        return task_to_dto(task)
