"""Search feature HTTP 层的模型转换。"""

from __future__ import annotations

from fileseek.features.search.application.queries import SearchFilesQuery,FileSortBy,SortOrder
from fileseek.features.search.application.dto import SearchResultsDTO
from fileseek.features.search.interfaces.http.schemas import (
    SearchRequest,SearchResponse,FileItem
)
from fileseek.shared.domain.file_types import FileCategory

def search_request_to_query(body: SearchRequest) -> SearchFilesQuery:
    """把 HTTP 请求转成应用层查询。

    无法识别的 file_types 取值会被丢弃。全部取值都无法识别时传空列表而不是 None，
    让用例知道这是"限定为空集"而不是"未限定"——否则筛错类型反而会搜出全部类型。

    这里必须转成 `FileType` 枚举而不是把字符串原样传下去：向量库按枚举取 collection
    （`ChromaVectorStore._collections.get(file_type)`），拿到字符串会一条都取不到，
    表现成"筛了类型就搜不出东西"。
    """
    categories = [FileCategory(category) for category in body.categories if category in list(FileCategory)]
    return SearchFilesQuery(
        query=body.query,
        tag=body.tag,
        folder_id=body.folder_id,
        categories=categories,
        name_query=body.name_query,
        min_size_m=body.min_size_m,
        max_size_m=body.max_size_m,
        start_date=body.start_date,
        end_date=body.end_date,
        page_number=body.page_number,
        page_size=body.page_size,
        sort_by=FileSortBy(body.sort_by),
        sort_order=SortOrder(body.sort_order)
    )

def search_result_to_response(result: SearchResultsDTO) -> SearchResponse:
    """将搜索结果 DTO 转换成 API Response。"""

    offset = (result.page_number - 1) * result.page_size
    has_more = offset + result.page_size < result.total

    items = [
        FileItem.model_validate(item)
        for item in result.items
    ]
    return SearchResponse(
        items=items,
        counter=result.counter,
        page_number=result.page_number,
        page_size=result.page_size,
        total=result.total,
        has_more=has_more,
    )