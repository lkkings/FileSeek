from __future__ import annotations

from fastapi import Request

from fileseek.features.tasks.application.use_cases import (
    CancelTaskUseCase,
    DeleteTaskUseCase,
    ListTasksUseCase,
    RetryTaskUseCase,
)
from fileseek.shared.application.dependencies import resolve_dependency


def get_list_tasks_use_case(request: Request) -> ListTasksUseCase:
    return resolve_dependency(request, "list_tasks_use_case")


def get_retry_task_use_case(request: Request) -> RetryTaskUseCase:
    return resolve_dependency(request, "retry_task_use_case")


def get_delete_task_use_case(request: Request) -> DeleteTaskUseCase:
    return resolve_dependency(request, "delete_task_use_case")


def get_cancel_task_use_case(request: Request) -> CancelTaskUseCase:
    return resolve_dependency(request, "cancel_task_use_case")
