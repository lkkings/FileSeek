from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from fileseek.features.recent.application.use_cases import (
    DeleteRecentAccessUseCase,
    ListRecentAccessUseCase,
    RecordAccessUseCase,
)
from fileseek.features.recent.interfaces.http.dependencies import (
    get_delete_recent_access_use_case,
    get_list_recent_access_use_case,
    get_record_access_use_case,
)
from fileseek.features.recent.interfaces.http.mappers import (
    list_recent_query,
    recent_access_page_to_response,
    record_access_command,
)
from fileseek.features.recent.interfaces.http.schemas import (
    RecordAccessRequest,
)
from fileseek.shared.envelope import success_response

router = APIRouter(
    prefix="/recent",
    tags=["Recent"],
)


@router.get("")
async def list_recent_access(
    use_case: Annotated[
        ListRecentAccessUseCase,
        Depends(get_list_recent_access_use_case),
    ],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict[str, object]:
    """分页列出最近访问的文件。"""
    records, total = await use_case.execute(list_recent_query(page, page_size))

    return success_response(
        recent_access_page_to_response(records, total, page, page_size)
    )


@router.post("")
async def record_access(
    request_body: RecordAccessRequest,
    use_case: Annotated[
        RecordAccessUseCase,
        Depends(get_record_access_use_case),
    ],
) -> dict[str, object]:
    """添加最近访问记录。"""
    await use_case.execute(record_access_command(request_body.file_id))
    return success_response(None)


@router.delete("/{record_id}")
async def delete_recent_access(
    record_id: int,
    use_case: Annotated[
        DeleteRecentAccessUseCase,
        Depends(get_delete_recent_access_use_case),
    ],
) -> dict[str, object]:
    """删除最近访问记录。"""
    await use_case.execute(record_id)
    return success_response(None)
