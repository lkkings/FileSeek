"""Search feature HTTP 路由。"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse, StreamingResponse

from fileseek.features.search.application.dto import EnhancedSearchProgressDTO
from fileseek.features.search.application.use_cases import EnhancedSearchUseCase, SearchFilesUseCase
from fileseek.features.search.infrastructure.query_worker import QueryEmbeddingClient
from fileseek.features.search.interfaces.http.dependencies import (
    get_enhanced_search_use_case,
    get_query_embedding_client,
    get_search_files_use_case,
)
from fileseek.features.search.interfaces.http.mappers import (
    enhanced_search_progress_to_event,
    enhanced_search_request_to_query,
    search_request_to_query,
    search_result_to_response,
)
from fileseek.features.search.interfaces.http.schemas import EnhancedSearchRequest, SearchRequest
from fileseek.shared.domain.exceptions import ApplicationError
from fileseek.shared.envelope import error_response, success_response

router = APIRouter(tags=["Search"])

PROGRESS_KEEPALIVE_SECONDS = 15


@router.post("/search")
async def search(
    body: SearchRequest,
    use_case: Annotated[SearchFilesUseCase, Depends(get_search_files_use_case)],
) -> dict[str, Any]:
    """
    执行文件搜索
    """
    result = await use_case.execute(search_request_to_query(body))
    data = search_result_to_response(result)
    return success_response(data=data)


@router.post("/search/enhanced")
async def enhanced_search(
    body: EnhancedSearchRequest,
    use_case: Annotated[EnhancedSearchUseCase, Depends(get_enhanced_search_use_case)],
) -> dict[str, Any]:
    """
    执行检索增强搜索
    """
    try:
        result = await use_case.execute(enhanced_search_request_to_query(body))
    except ApplicationError as exc:
        return error_response(str(exc))
    return success_response(data=search_result_to_response(result))


@router.post("/search/enhanced/stream")
async def enhanced_search_stream(
    body: EnhancedSearchRequest,
    use_case: Annotated[EnhancedSearchUseCase, Depends(get_enhanced_search_use_case)],
) -> StreamingResponse:
    """以 SSE 返回检索增强搜索过程和最终结果。"""

    async def stream() -> AsyncIterator[str]:
        events = use_case.execute_stream(enhanced_search_request_to_query(body))
        next_event: asyncio.Task[EnhancedSearchProgressDTO] | None = None
        try:
            next_event = asyncio.ensure_future(anext(events))
            while True:
                try:
                    event = await asyncio.wait_for(
                        asyncio.shield(next_event),
                        timeout=PROGRESS_KEEPALIVE_SECONDS,
                    )
                except TimeoutError:
                    yield ": ping\n\n"
                    continue
                except StopAsyncIteration:
                    break
                yield _format_progress_event(event)
                if event.type in {"result", "error"}:
                    return
                next_event = asyncio.ensure_future(anext(events))
        finally:
            if next_event is not None and not next_event.done():
                next_event.cancel()
            await events.aclose()

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def _format_progress_event(event: EnhancedSearchProgressDTO) -> str:
    payload = enhanced_search_progress_to_event(event).model_dump_json()
    return f"event: progress\ndata: {payload}\n\n"


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
