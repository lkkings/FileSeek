"""Search feature HTTP 层的模型转换。"""

from __future__ import annotations

from fileseek.features.search.application.dto import (
    EnhancedSearchProgressDTO,
    SearchResultsDTO,
)
from fileseek.features.search.application.mappers import (
    search_request_to_query as application_search_request_to_query,
)
from fileseek.features.search.application.queries import (
    EnhancedSearchQuery,
    FileSortBy,
    SearchFilesQuery,
    SortOrder,
)
from fileseek.features.search.interfaces.http.schemas import (
    EnhancedSearchProgressEvent,
    EnhancedSearchRequest,
    FileItem,
    SearchRequest,
    SearchResponse,
)


def search_request_to_query(body: SearchRequest) -> SearchFilesQuery:
    """把共享搜索请求转成应用层查询。"""
    return application_search_request_to_query(body)


def enhanced_search_request_to_query(body: EnhancedSearchRequest) -> EnhancedSearchQuery:
    return EnhancedSearchQuery(
        query=body.query,
        folder_id=body.folder_id,
        page_number=body.page_number,
        page_size=body.page_size,
        sort_by=FileSortBy(body.sort_by),
        sort_order=SortOrder(body.sort_order),
    )


def search_result_to_response(result: SearchResultsDTO) -> SearchResponse:
    """将搜索结果 DTO 转换成 API Response。"""

    offset = (result.page_number - 1) * result.page_size
    has_more = offset + result.page_size < result.total

    items = [FileItem.model_validate(item) for item in result.items]
    return SearchResponse(
        items=items,
        counter=result.counter,
        page_number=result.page_number,
        page_size=result.page_size,
        total=result.total,
        has_more=has_more,
    )


def enhanced_search_progress_to_event(
    event: EnhancedSearchProgressDTO,
) -> EnhancedSearchProgressEvent:
    """Convert an application progress event to its whitelisted API shape."""

    return EnhancedSearchProgressEvent(
        type=event.type,
        phase=event.phase,
        message=event.message,
        round_number=event.round_number,
        content=event.content,
        tool_name=event.tool_name,
        query=event.query,
        categories=list(event.categories),
        name_query=event.name_query,
        candidate_count=event.candidate_count,
        total=event.total,
        result=(search_result_to_response(event.result) if event.result is not None else None),
        error=event.error,
    )
