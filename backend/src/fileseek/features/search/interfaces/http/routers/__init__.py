"""Search feature HTTP 路由。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from fileseek.features.search.application.use_cases import SearchFilesUseCase
from fileseek.features.search.interfaces.http.dependencies import get_search_files_use_case
from fileseek.features.search.interfaces.http.mappers import (
    search_request_to_query,search_result_to_response
)
from fileseek.features.search.interfaces.http.schemas import (
    SearchRequest
)
from fileseek.shared.envelope import success_response

router = APIRouter(tags=["Search"])

@router.post("/search")
async def search(
    body: SearchRequest,
    use_case: Annotated[SearchFilesUseCase, Depends(get_search_files_use_case)],
):
    """
    执行文件搜索
    """
    result = await use_case.execute(search_request_to_query(body))
    data = search_result_to_response(result)
    return success_response(data=data)
