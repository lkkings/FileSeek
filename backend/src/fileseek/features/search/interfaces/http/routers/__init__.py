"""Search feature HTTP 路由。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse

from fileseek.features.search.application.use_cases import SearchFilesUseCase
from fileseek.features.search.infrastructure.query_worker import QueryEmbeddingClient
from fileseek.features.search.interfaces.http.dependencies import (
    get_query_embedding_client,
    get_search_files_use_case,
)
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


@router.post("/search/warmup", status_code=202)
async def warmup(
    client: Annotated[QueryEmbeddingClient, Depends(get_query_embedding_client)],
) -> JSONResponse:
    """
    预热查询模型：进程不在就拉起来，模型在子进程里后台加载，本接口立即返回。

    前端在搜索框获得焦点时调用，用户敲完回车时模型多半已经就绪，省掉冷启动的等待。
    """
    started = await run_in_threadpool(client.ensure_started)
    return JSONResponse(success_response(data={"started": started}), status_code=202)
