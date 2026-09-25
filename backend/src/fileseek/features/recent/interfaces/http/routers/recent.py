from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from fileseek.features.recent.application.use_cases import (
    ListRecentAccessUseCase,
)
from fileseek.features.recent.interfaces.http.dependencies import (
    get_list_recent_access_use_case,
)
from fileseek.features.recent.interfaces.http.mappers import list_recent_query
from fileseek.features.recent.interfaces.http.schemas import RecentAccessResponse
from fileseek.shared.envelope import success_response

router = APIRouter(
    prefix="/library/recent",
    tags=["library"],
)


@router.get("")
async def list_recent_access(
    use_case: Annotated[
        ListRecentAccessUseCase,
        Depends(get_list_recent_access_use_case),
    ],
    limit: int = Query(20, ge=1, le=100),
) -> dict[str, object]:
    """列出最近访问的文件。"""
    records = await use_case.execute(list_recent_query(limit))

    return success_response(
        [
            RecentAccessResponse(file_id=record.file_id, accessed_at=record.accessed_at)
            for record in records
        ],
    )
