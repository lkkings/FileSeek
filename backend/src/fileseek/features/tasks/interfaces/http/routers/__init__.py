from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from fileseek.features.tasks.application.use_cases import (
    DeleteTaskUseCase,
    ListTasksUseCase,
    RetryTaskUseCase,
)
from fileseek.features.tasks.application.queries import ListTasksQuery
from fileseek.features.tasks.interfaces.http.dependencies import (
    get_delete_task_use_case,
    get_list_tasks_use_case,
    get_retry_task_use_case,
)
from fileseek.features.tasks.interfaces.http.mappers import (
    delete_task_to_command,
    retry_task_to_command,
    task_list_to_schema,
    task_to_schema,
)
from fileseek.shared.envelope import (
    success_response,
)

router = APIRouter(
    prefix="/tasks",
    tags=["Tasks"],
)


@router.get("")
async def list_tasks(
    use_case: Annotated[
        ListTasksUseCase,
        Depends(get_list_tasks_use_case),
    ],
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> dict[str, object]:
    """列出任务队列（分页），附带各状态计数。"""
    result = await use_case.execute(ListTasksQuery(status=status, page=page, page_size=page_size))

    return success_response(task_list_to_schema(result, page, page_size))


@router.post("/{task_id}/retry")
async def retry_task(
    task_id: str,
    use_case: Annotated[
        RetryTaskUseCase,
        Depends(get_retry_task_use_case),
    ],
) -> dict[str, object]:
    """重试失败的任务。"""
    task = await use_case.execute(retry_task_to_command(task_id))

    return success_response(
        task_to_schema(task),
    )


@router.delete("/{task_id}")
async def delete_task(
    task_id: str,
    use_case: Annotated[
        DeleteTaskUseCase,
        Depends(get_delete_task_use_case),
    ],
) -> dict[str, object]:
    """从任务队列移除非处理中的任务。"""
    await use_case.execute(delete_task_to_command(task_id))
    return success_response(None)
