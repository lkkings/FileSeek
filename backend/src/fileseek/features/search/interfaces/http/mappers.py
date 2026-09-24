"""Search feature HTTP 层的模型转换。"""

from __future__ import annotations

from fileseek.features.search.application.dto import SearchFileMetadata
from fileseek.features.search.application.queries import SearchFilesQuery
from fileseek.features.search.domain.entities import SearchResult
from fileseek.features.search.interfaces.http.schemas import (
    DocumentSearchResult,
    ImageSearchResult,
    SearchRequest,
    VideoSearchResult,
)
from fileseek.shared.domain.file_types import FileType

# 预览路由挂在 api_prefix 下（`bootstrap/app.py`），所以这里必须带上前缀，否则
# `preview_url` 指向的是一个不存在的路径，照着它取内容只会拿到 404。
_PREVIEW_PATH = "/api/v1/library/files/preview"

_VALID_FILE_TYPES = {file_type.value for file_type in FileType}


def search_request_to_query(body: SearchRequest) -> SearchFilesQuery:
    """把 HTTP 请求转成应用层查询。

    无法识别的 file_types 取值会被丢弃。全部取值都无法识别时传空列表而不是 None，
    让用例知道这是"限定为空集"而不是"未限定"——否则筛错类型反而会搜出全部类型。

    这里必须转成 `FileType` 枚举而不是把字符串原样传下去：向量库按枚举取 collection
    （`ChromaVectorStore._collections.get(file_type)`），拿到字符串会一条都取不到，
    表现成"筛了类型就搜不出东西"。
    """
    file_types = [
        FileType(value) for value in body.file_types if value in _VALID_FILE_TYPES
    ]
    return SearchFilesQuery(
        query=body.query,
        file_types=file_types,
        limit=body.limit,
        name_query=body.name_query,
        min_size_m=body.min_size_m,
        max_size_m=body.max_size_m,
        start_date=body.start_date,
        end_date=body.end_date,
    )


def search_result_to_schema(
    result: SearchResult,
    metadata: SearchFileMetadata | None,
    preview_url_base: str,
) -> DocumentSearchResult | ImageSearchResult | VideoSearchResult:
    """把搜索结果转成对应媒体类型的响应模型。

    Args:
        result: 搜索结果实体
        metadata: 文件元数据；为 None 时 path 回退空串、accessible 回退 False，
            因为拿不到元数据就无法判断文件还在不在
        preview_url_base: 预览地址的 scheme + host + port 前缀，不含结尾斜杠

    Returns:
        DocumentSearchResult / ImageSearchResult / VideoSearchResult
    """
    file_id = result.file_id
    filename = result.file_name
    preview_url = f"{preview_url_base}{_PREVIEW_PATH}/{file_id}"
    score = result.score
    path = metadata.path if metadata else ""
    accessible = metadata.accessible if metadata else False

    if result.file_type == FileType.DOCUMENT:
        return DocumentSearchResult(
            file_id=file_id,
            filename=filename,
            preview_url=preview_url,
            score=score,
            path=path,
            accessible=accessible,
            matched_text=result.snippet,
            page_number=result.page_number,
            line_number=result.line_number,
        )
    if result.file_type == FileType.IMAGE:
        return ImageSearchResult(
            file_id=file_id,
            filename=filename,
            preview_url=preview_url,
            score=score,
            path=path,
            accessible=accessible,
        )
    return VideoSearchResult(
        file_id=file_id,
        filename=filename,
        preview_url=preview_url,
        score=score,
        path=path,
        accessible=accessible,
        # 契约把起止时间定义为整数秒，向量元数据里可能是浮点。
        start_time=int(result.start_time) if result.start_time is not None else None,
        end_time=int(result.end_time) if result.end_time is not None else None,
    )
