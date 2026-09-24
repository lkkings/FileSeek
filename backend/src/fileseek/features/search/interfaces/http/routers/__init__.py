"""Search feature HTTP 路由。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from fileseek.features.search.application import SearchFilesUseCase
from fileseek.features.search.interfaces.http.dependencies import get_search_files_use_case
from fileseek.features.search.interfaces.http.mappers import (
    search_request_to_query,
    search_result_to_schema,
)
from fileseek.features.search.interfaces.http.schemas import (
    DocumentSearchResult,
    ImageSearchResult,
    SearchError,
    SearchRequest,
    SearchResponse,
    SearchResponseData,
    VideoSearchResult,
)

router = APIRouter(tags=["search"])

_INVALID_QUERY_MESSAGE = "query cannot be empty or contain only whitespace characters"


@router.post("/search", response_model=SearchResponse)
async def search(
    body: SearchRequest,
    request: Request,
    use_case: Annotated[SearchFilesUseCase, Depends(get_search_files_use_case)],
) -> SearchResponse | JSONResponse:
    """执行多模态搜索与高级筛选。

    `limit` 对每种媒体类型独立生效：三种类型都搜时最多返回 3 * limit 条结果。
    某一类型无命中时对应数组为 `[]`，不影响其它类型。
    """
    if not body.query.strip():
        # 这一条不能抛异常交给全局 handler：全局 handler 返回的 error 是字符串，
        # 而契约要求 `{code, message}`。
        return JSONResponse(
            SearchResponse(
                status="error",
                data=None,
                error=SearchError(code="INVALID_QUERY", message=_INVALID_QUERY_MESSAGE),
            ).model_dump(),
            status_code=400,
        )

    # 预览地址要能被前端直接取用，而后端端口是启动时动态选的（见 main.find_free_port），
    # 写死 host:port 在运行期一定是错的，所以从当前请求的 base_url 推。
    preview_url_base = str(request.base_url).rstrip("/")

    documents: list[DocumentSearchResult] = []
    images: list[ImageSearchResult] = []
    videos: list[VideoSearchResult] = []

    for result, metadata in await use_case.execute(search_request_to_query(body)):
        schema = search_result_to_schema(result, metadata, preview_url_base)
        # 按实际类型分派，而不是查一个异构的 dict：后者会把三个列表的元素类型擦成
        # 公共父类，类型检查就再也拦不住"把视频结果塞进文档数组"这种错。
        if isinstance(schema, DocumentSearchResult):
            documents.append(schema)
        elif isinstance(schema, ImageSearchResult):
            images.append(schema)
        else:
            videos.append(schema)

    return SearchResponse(
        status="success",
        data=SearchResponseData(documents=documents, images=images, videos=videos),
        error=None,
    )
