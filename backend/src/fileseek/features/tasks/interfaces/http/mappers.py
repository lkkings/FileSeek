from __future__ import annotations

from fileseek.features.tasks.application.commands import (
    CancelTaskCommand,
    DeleteTaskCommand,
    RetryTaskCommand,
)
from fileseek.features.tasks.application.dto import (
    TaskDTO,
    TaskListDTO,
)
from fileseek.features.tasks.interfaces.http.schemas import (
    TaskListResponse,
    TaskResponse,
)


def task_to_schema(task: TaskDTO) -> TaskResponse:
    return TaskResponse(
        id=task.id,
        file=task.file,
        status=task.status,
        progress=task.progress,
        completed_count=task.completed_count,
        total_count=task.total_count,
        stage=task.stage,
        error_message=task.error_message,
        created_at=task.created_at,
    )


def retry_task_to_command(task_id: str) -> RetryTaskCommand:
    return RetryTaskCommand(task_id=task_id)


def delete_task_to_command(task_id: str) -> DeleteTaskCommand:
    return DeleteTaskCommand(task_id=task_id)


def cancel_task_to_command(task_id: str) -> CancelTaskCommand:
    return CancelTaskCommand(task_id=task_id)



def task_list_to_schema(value: TaskListDTO, page: int, page_size: int) -> TaskListResponse:
    return TaskListResponse(
        tasks=[task_to_schema(task) for task in value.tasks],
        counts=value.counts,
        page=page,
        page_size=page_size,
        total=value.total
    )
