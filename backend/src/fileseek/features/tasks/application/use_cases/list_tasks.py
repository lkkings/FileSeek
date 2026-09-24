from fileseek.features.tasks.application.dto import TaskListDTO
from fileseek.features.tasks.application.mappers import task_to_dto
from fileseek.features.tasks.application.queries import ListTasksQuery
from fileseek.features.tasks.domain.entities import TaskStatus
from fileseek.features.tasks.domain.repositories import TaskRepository

# 统计各状态计数时一次性拉取的上限，避免逐状态查询。
_COUNT_SCAN_LIMIT = 10000


class ListTasksUseCase:
    def __init__(self, task_repo: TaskRepository) -> None:
        self.task_repo = task_repo

    async def execute(
        self,
        query: ListTasksQuery,
    ) -> TaskListDTO:
        status_filter, page, page_size = query.status, query.page, query.page_size
        tasks, total = await self.task_repo.list_all(
            status_filter,
            page,
            page_size,
        )

        all_tasks, _ = await self.task_repo.list_all(
            None,
            1,
            _COUNT_SCAN_LIMIT,
        )

        counts = {
            status.value: sum(1 for task in all_tasks if task.status == status)
            for status in TaskStatus
        }

        return TaskListDTO(tasks=[task_to_dto(task) for task in tasks], total=total, counts=counts)
