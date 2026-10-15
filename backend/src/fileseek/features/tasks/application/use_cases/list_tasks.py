from fileseek.features.tasks.application.dto import TaskListDTO
from fileseek.features.tasks.application.mappers import task_to_dto
from fileseek.features.tasks.application.queries import ListTasksQuery
from fileseek.features.tasks.domain.repositories import TaskRepository
from fileseek.features.tasks.domain.entities import TaskStatus


class ListTasksUseCase:
    def __init__(self, task_repo: TaskRepository) -> None:
        self.task_repo = task_repo

    async def execute(
        self,
        query: ListTasksQuery,
    ) -> TaskListDTO:
        status = TaskStatus(query.status) if query.status else None
        tasks, total = await self.task_repo.list_all(
            status=status,
            page=query.page,
            page_size=query.page_size,
        )

        status_counts = await self.task_repo.count_by_status()

        counts = {status.value: count for status, count in status_counts.items()}

        return TaskListDTO(
            tasks=[task_to_dto(task) for task in tasks],
            total=total,
            counts=counts,
        )
