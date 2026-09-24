"""搜索 API 用例。

embedder 和向量库都被换成假实现（见 tests/api/conftest.py）：真货会去下载
jina-clip-v2 权重、开一个 Chroma 客户端。这里验的是路由契约——入参怎么传到用例、
结果怎么映射回响应。

两件和其它接口不同的事：

- **响应信封不一样。** search 自带一个 `SearchResponse`，`error` 是 `{code, message}`
  对象而不是字符串（见 `features/search/interfaces/http/schemas`）。
- **没有分页。** 请求只有 `limit`（每种媒体类型各自的 Top N），响应没有 `has_more_*`。

还有一个刻意的行为：嵌入模型没接入时 `SearchFilesUseCase` 捕获 NotImplementedError 并
返回空结果，而不是 500。所以"搜不到"和"模型没就位"在响应上长得一样，这是现有契约。
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from tests.api.conftest import API, FakeEmbedder, FakeVectorStore

from fileseek.features.tasks.domain.ports import VectorHit
from fileseek.shared.domain.file_types import FileType

SEARCH = f"{API}/search"

EMPTY_DATA = {"documents": [], "images": [], "videos": []}


def _hit(
    file_id: str = "file_1",
    file_name: str = "report.pdf",
    file_type: FileType = FileType.DOCUMENT,
    score: float = 87.0,
    **overrides: object,
) -> VectorHit:
    """造一条向量库命中。元信息随向量落盘，所以这里要给全。"""
    fields: dict[str, object] = {
        "file_id": file_id,
        "file_name": file_name,
        "file_type": file_type,
        "score": score,
        "path": f"/library/{file_name}",
        "size": 2048,
        "modified": "2026-01-01T00:00:00+00:00",
        "accessible": True,
    }
    fields.update(overrides)
    return VectorHit(**fields)  # type: ignore[arg-type]


def test_search_empty_results(client: TestClient) -> None:
    body = client.post(SEARCH, json={"query": "报告"}).json()

    assert body["status"] == "success"
    assert body["data"] == EMPTY_DATA
    assert body["error"] is None


def test_document_result_shape(
    client: TestClient, fake_vector_store: FakeVectorStore
) -> None:
    """文档命中带回命中文本和页/行号——前端靠它跳到原文位置。"""
    fake_vector_store.results = [
        _hit(snippet="季度营收同比增长", page_number=3, line_number=15)
    ]

    body = client.post(SEARCH, json={"query": "营收"}).json()

    result = body["data"]["documents"][0]
    assert result["file_id"] == "file_1"
    # 文件名字段是 `filename`，不是 `file_name`。
    assert result["filename"] == "report.pdf"
    assert result["score"] == 87.0
    # 路径字段是 `path`。
    assert result["path"] == "/library/report.pdf"
    assert result["accessible"] is True
    assert result["matched_text"] == "季度营收同比增长"
    assert result["page_number"] == 3
    assert result["line_number"] == 15
    # 预览地址由路由按当次请求的 base_url 拼出来，因为端口是启动时动态选的。
    assert result["preview_url"].endswith("/api/v1/library/files/preview/file_1")


def test_video_result_carries_a_flat_moment(
    client: TestClient, fake_vector_store: FakeVectorStore
) -> None:
    """视频命中是一对起止时间，不是片段数组。"""
    fake_vector_store.results = [
        _hit(
            file_id="vid_1",
            file_name="ride.mp4",
            file_type=FileType.VIDEO,
            start_time=83.5,
            end_time=120.0,
        )
    ]

    result = client.post(SEARCH, json={"query": "骑行"}).json()["data"]["videos"][0]

    # 契约把起止时间定义为整数秒，向量元数据里可能是浮点。
    assert result["start_time"] == 83
    assert result["end_time"] == 120
    assert "segments" not in result


def test_image_result_has_only_the_common_fields(
    client: TestClient, fake_vector_store: FakeVectorStore
) -> None:
    fake_vector_store.results = [
        _hit(file_id="img_1", file_name="cat.jpg", file_type=FileType.IMAGE)
    ]

    result = client.post(SEARCH, json={"query": "猫"}).json()["data"]["images"][0]

    assert result["file_id"] == "img_1"
    assert "matched_text" not in result
    assert "start_time" not in result


def test_search_passes_query_to_embedder(
    client: TestClient, fake_embedder: FakeEmbedder
) -> None:
    client.post(SEARCH, json={"query": "会议记录"})

    assert fake_embedder.calls == ["会议记录"]


def test_search_defaults_to_all_file_types(
    client: TestClient, fake_vector_store: FakeVectorStore
) -> None:
    client.post(SEARCH, json={"query": "x"})

    _, file_types, _, _ = fake_vector_store.calls[0]
    assert set(file_types) == {FileType.DOCUMENT, FileType.IMAGE, FileType.VIDEO}


def test_search_honours_the_file_type_filter(
    client: TestClient, fake_vector_store: FakeVectorStore
) -> None:
    """请求字段是 `file_types`，不是 `media_types`。"""
    client.post(SEARCH, json={"query": "x", "file_types": ["image"]})

    _, file_types, _, _ = fake_vector_store.calls[0]
    assert file_types == [FileType.IMAGE]


def test_search_passes_the_limit_through(
    client: TestClient, fake_vector_store: FakeVectorStore
) -> None:
    """limit 是每种媒体类型各自的 Top N，默认 20。"""
    client.post(SEARCH, json={"query": "x", "limit": 5})

    _, _, limit, _ = fake_vector_store.calls[0]
    assert limit == 5


def test_size_filters_are_converted_to_bytes(
    client: TestClient, fake_vector_store: FakeVectorStore
) -> None:
    """请求里的单位是 MB（`min_size_m`），下推给向量库时换成字节。"""
    client.post(SEARCH, json={"query": "x", "min_size_m": 1.0, "max_size_m": 10.0})

    _, _, _, filters = fake_vector_store.calls[0]
    assert filters is not None
    assert filters.min_size == 1024 * 1024
    assert filters.max_size == 10 * 1024 * 1024


def test_advanced_filters_are_pushed_down(
    client: TestClient, fake_vector_store: FakeVectorStore
) -> None:
    client.post(
        SEARCH,
        json={
            "query": "x",
            "name_query": "2024",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
        },
    )

    _, _, _, filters = fake_vector_store.calls[0]
    assert filters is not None
    assert filters.name_query == "2024"
    assert filters.start_date == "2024-01-01"
    assert filters.end_date == "2024-12-31"


def test_blank_query_is_refused_with_a_structured_error(client: TestClient) -> None:
    """空白查询返回 400 和 `{code, message}`——search 的 error 不是字符串。"""
    response = client.post(SEARCH, json={"query": "   "})

    assert response.status_code == 400
    body = response.json()
    assert body["status"] == "error"
    assert body["data"] is None
    assert body["error"]["code"] == "INVALID_QUERY"
    assert body["error"]["message"]


def test_missing_query_is_rejected(client: TestClient) -> None:
    """`query` 是必填的。"""
    assert client.post(SEARCH, json={}).status_code == 422


def test_search_rejects_a_zero_limit(client: TestClient) -> None:
    assert client.post(SEARCH, json={"query": "x", "limit": 0}).status_code == 422


def test_search_rejects_a_negative_size_filter(client: TestClient) -> None:
    assert client.post(SEARCH, json={"query": "x", "min_size_m": -1}).status_code == 422


def test_search_returns_empty_when_the_model_is_missing(
    client: TestClient, fake_embedder: FakeEmbedder, monkeypatch: object
) -> None:
    """模型未接入 → 空结果而不是 500，见模块 docstring。"""

    def raise_not_implemented(_texts: str) -> list[float]:
        raise NotImplementedError("jina-clip-v2 尚未接入")

    monkeypatch.setattr(fake_embedder, "embed_text", raise_not_implemented)  # type: ignore[attr-defined]

    response = client.post(SEARCH, json={"query": "x"})

    assert response.status_code == 200
    assert response.json()["data"] == EMPTY_DATA
