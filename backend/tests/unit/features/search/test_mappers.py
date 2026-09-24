"""Search HTTP 映射的用例。

这里验的是契约字段：`filename` / `matched_text` / `accessible` 这些名字前端直接按名取，
改一个就是破坏性变更。
"""

from __future__ import annotations

from fileseek.features.search.application.dto import SearchFileMetadata
from fileseek.features.search.domain.entities import SearchResult
from fileseek.features.search.interfaces.http.mappers import (
    search_request_to_query,
    search_result_to_schema,
)
from fileseek.features.search.interfaces.http.schemas import SearchRequest
from fileseek.shared.domain.file_types import FileType

BASE = "http://127.0.0.1:3000"


def metadata(path: str = "/lib/a.pdf", *, accessible: bool = True) -> SearchFileMetadata:
    return SearchFileMetadata(
        path=path,
        size=2048,
        modified="2026-01-01T00:00:00+00:00",
        accessible=accessible,
    )


def test_document_result_carries_text_location() -> None:
    result = SearchResult(
        file_id="doc-1",
        file_name="Q2.pdf",
        file_type=FileType.DOCUMENT,
        score=94.5,
        snippet="季度营收",
        page_number=2,
        line_number=15,
    )

    schema = search_result_to_schema(result, metadata(), BASE).model_dump()

    assert schema == {
        "file_id": "doc-1",
        "filename": "Q2.pdf",
        # 带 api_prefix：不带的话这个地址指向一个不存在的路由。
        "preview_url": f"{BASE}/api/v1/library/files/preview/doc-1",
        "score": 94.5,
        "path": "/lib/a.pdf",
        "accessible": True,
        "matched_text": "季度营收",
        "page_number": 2,
        "line_number": 15,
    }


def test_image_result_has_no_location_fields() -> None:
    result = SearchResult(
        file_id="img-1",
        file_name="cat.jpg",
        file_type=FileType.IMAGE,
        score=96.1,
    )

    schema = search_result_to_schema(result, metadata("/lib/cat.jpg"), BASE).model_dump()

    assert set(schema) == {
        "file_id",
        "filename",
        "preview_url",
        "score",
        "path",
        "accessible",
    }


def test_video_result_rounds_times_to_whole_seconds() -> None:
    """契约把起止时间定义为整数秒，向量元数据里可能是浮点。"""
    result = SearchResult(
        file_id="vid-1",
        file_name="ride.mp4",
        file_type=FileType.VIDEO,
        score=91.0,
        start_time=83.4,
        end_time=120.9,
    )

    schema = search_result_to_schema(result, metadata("/lib/ride.mp4"), BASE).model_dump()

    assert schema["start_time"] == 83
    assert schema["end_time"] == 120


def test_missing_metadata_reports_inaccessible() -> None:
    """拿不到元数据就无法判断文件还在不在，只能报 accessible=False。"""
    result = SearchResult(
        file_id="x",
        file_name="x.pdf",
        file_type=FileType.DOCUMENT,
        score=1.0,
    )

    schema = search_result_to_schema(result, None, BASE).model_dump()

    assert schema["accessible"] is False
    assert schema["path"] == ""


def test_inaccessible_file_is_still_returned() -> None:
    """文件不可访问仍然作为结果返回，由前端决定是否允许预览。"""
    result = SearchResult(
        file_id="gone",
        file_name="gone.pdf",
        file_type=FileType.DOCUMENT,
        score=50.0,
    )

    schema = search_result_to_schema(result, metadata(accessible=False), BASE).model_dump()

    assert schema["accessible"] is False
    assert schema["file_id"] == "gone"


def test_request_maps_advanced_filters() -> None:
    body = SearchRequest(
        query="猫咪 窗台",
        file_types=["document", "image", "video"],
        limit=20,
        name_query="jpg",
        min_size_m=1.0,
        max_size_m=500.0,
        start_date="2026-01-01",
        end_date="2026-09-20",
    )

    q = search_request_to_query(body)

    assert q.query == "猫咪 窗台"
    assert q.file_types == [FileType.DOCUMENT, FileType.IMAGE, FileType.VIDEO]
    assert q.limit == 20
    assert q.name_query == "jpg"
    assert q.min_size_m == 1.0
    assert q.max_size_m == 500.0
    assert q.start_date == "2026-01-01"
    assert q.end_date == "2026-09-20"


def test_unknown_file_types_are_dropped() -> None:
    q = search_request_to_query(SearchRequest(query="x", file_types=["nonsense", "image"]))

    assert q.file_types == [FileType.IMAGE]


def test_all_unknown_file_types_yield_empty_not_none() -> None:
    """全部无法识别时传空列表：None 会让用例退化成"搜全部"，等于忽略了筛选。"""
    q = search_request_to_query(SearchRequest(query="x", file_types=["nonsense"]))

    assert q.file_types == []


def test_file_types_default_to_all() -> None:
    q = search_request_to_query(SearchRequest(query="x"))

    assert q.file_types == [FileType.DOCUMENT, FileType.IMAGE, FileType.VIDEO]
