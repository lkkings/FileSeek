"""`POST /search` 的响应契约。

只装路由 + 依赖覆盖，不起 lifespan、不建库：验的是请求进到用例、结果映射回响应这条路，
以及 INVALID_QUERY 的错误形状。

向量库被换成假实现：真货会开一个 Chroma 客户端。元信息（path/accessible）现在随命中
一起从向量库回来，所以这里不再需要文件仓储——索引时就把这些字段写进向量元数据了。
索引到检索的真实往返在 `use_cases/test_search_files.py` 里用真的 Chroma 验。
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from fileseek.features.search.interfaces.http.dependencies import (
    get_embedder,
    get_vector_store,
)
from fileseek.features.search.interfaces.http.routers import router
from fileseek.features.tasks.domain.ports import VectorHit, VectorSearchFilters
from fileseek.shared.domain.file_types import FileType


class FakeEmbedder:
    def embed_text(self, text: str) -> list[float]:
        return [0.1, 0.2, 0.3]


class FakeVectorStore:
    """返回预置命中并记录调用参数的向量库。"""

    def __init__(self, hits: list[VectorHit]) -> None:
        self.hits = hits
        self.calls: list[tuple[list[FileType], int, VectorSearchFilters | None]] = []

    def search(
        self,
        query_vector: list[float],
        file_types: list[FileType],
        limit: int,
        filters: VectorSearchFilters | None = None,
    ) -> list[VectorHit]:
        self.calls.append((file_types, limit, filters))
        return [hit for hit in self.hits if hit.file_type in file_types]


def make_hit(
    file_id: str,
    file_name: str,
    file_type: FileType,
    score: float = 90.0,
    **extra: object,
) -> VectorHit:
    return VectorHit(
        file_id=file_id,
        file_name=file_name,
        file_type=file_type,
        score=score,
        path=f"/lib/{file_name}",
        size=2048,
        modified="2026-01-01T00:00:00+00:00",
        accessible=True,
        **extra,  # type: ignore[arg-type]
    )


def build_store(hits: list[VectorHit] | None = None) -> FakeVectorStore:
    return FakeVectorStore(hits or [])


def build_client(store: FakeVectorStore) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_embedder] = lambda: FakeEmbedder()
    app.dependency_overrides[get_vector_store] = lambda: store
    return TestClient(app)


@pytest.fixture
def store() -> FakeVectorStore:
    return build_store()


@pytest.fixture
def client(store: FakeVectorStore) -> TestClient:
    return build_client(store)


@pytest.mark.parametrize("bad_query", ["", "   ", "\n", "\t", " \n\t "])
def test_whitespace_only_query_is_rejected(client: TestClient, bad_query: str) -> None:
    response = client.post("/search", json={"query": bad_query})

    assert response.status_code == 400
    body = response.json()
    assert body["status"] == "error"
    assert body["data"] is None
    assert body["error"]["code"] == "INVALID_QUERY"


def test_missing_query_is_a_validation_error(client: TestClient) -> None:
    """query 是必填项，整个字段缺失走 FastAPI 的 422。"""
    assert client.post("/search", json={}).status_code == 422


def test_empty_buckets_are_arrays_not_null(client: TestClient) -> None:
    body = client.post("/search", json={"query": "猫咪"}).json()

    assert body["status"] == "success"
    assert body["error"] is None
    assert body["data"] == {"documents": [], "images": [], "videos": []}


def test_results_are_grouped_by_file_type() -> None:
    store = build_store(
        [
            make_hit(
                "doc-1",
                "Q2.pdf",
                FileType.DOCUMENT,
                94.5,
                snippet="季度营收",
                page_number=2,
                line_number=15,
            ),
            make_hit("img-1", "cat.jpg", FileType.IMAGE, 96.1),
            make_hit(
                "vid-1", "ride.mp4", FileType.VIDEO, 91.0, start_time=83.0, end_time=120.0
            ),
        ]
    )

    data = build_client(store).post("/search", json={"query": "猫咪 窗台"}).json()["data"]

    assert [d["file_id"] for d in data["documents"]] == ["doc-1"]
    assert [i["file_id"] for i in data["images"]] == ["img-1"]
    assert [v["file_id"] for v in data["videos"]] == ["vid-1"]

    document = data["documents"][0]
    assert document["filename"] == "Q2.pdf"
    assert document["matched_text"] == "季度营收"
    assert document["page_number"] == 2
    assert document["line_number"] == 15
    assert document["path"] == "/lib/Q2.pdf"
    assert document["accessible"] is True

    assert data["videos"][0]["start_time"] == 83
    assert data["videos"][0]["end_time"] == 120


def test_metadata_comes_from_the_vector_hit() -> None:
    """path / accessible 直接取自向量元数据，不回库表。"""
    store = build_store(
        [
            VectorHit(
                file_id="gone",
                file_name="gone.pdf",
                file_type=FileType.DOCUMENT,
                score=50.0,
                path="/lib/gone.pdf",
                size=None,
                modified=None,
                accessible=False,
            )
        ]
    )

    document = build_client(store).post("/search", json={"query": "x"}).json()["data"][
        "documents"
    ][0]

    assert document["path"] == "/lib/gone.pdf"
    assert document["accessible"] is False


def test_preview_url_follows_the_serving_host() -> None:
    """后端端口是启动时动态选的，预览地址必须跟随当前请求，不能写死。"""
    store = build_store([make_hit("doc-1", "Q2.pdf", FileType.DOCUMENT)])

    document = build_client(store).post("/search", json={"query": "x"}).json()["data"][
        "documents"
    ][0]

    assert document["preview_url"].endswith("/api/v1/library/files/preview/doc-1")
    assert document["preview_url"].startswith("http://testserver")


def test_file_type_filter_limits_returned_buckets() -> None:
    """只搜 image 时，文档命中不该出现在响应里。"""
    store = build_store(
        [
            make_hit("doc-1", "Q2.pdf", FileType.DOCUMENT, 99.0),
            make_hit("img-1", "cat.jpg", FileType.IMAGE, 90.0),
        ]
    )

    data = build_client(store).post(
        "/search", json={"query": "猫咪", "file_types": ["image"]}
    ).json()["data"]

    assert data["documents"] == []
    assert [i["file_id"] for i in data["images"]] == ["img-1"]
    assert store.calls[0][0] == [FileType.IMAGE]


def test_advanced_filters_are_pushed_down_to_the_vector_store(
    client: TestClient, store: FakeVectorStore
) -> None:
    """筛选条件必须进到向量库那一次 query 里，不能在结果上后筛——见用例模块 docstring。"""
    client.post(
        "/search",
        json={
            "query": "报告",
            "name_query": "2026",
            "min_size_m": 1.0,
            "max_size_m": 10.0,
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
        },
    )

    _, _, filters = store.calls[0]
    assert filters is not None
    assert filters.name_query == "2026"
    # MB → 字节在用例层换算。
    assert filters.min_size == 1024 * 1024
    assert filters.max_size == 10 * 1024 * 1024
    assert filters.start_date == "2026-01-01"
    assert filters.end_date == "2026-12-31"


def test_limit_is_forwarded_per_file_type(client: TestClient, store: FakeVectorStore) -> None:
    client.post("/search", json={"query": "x", "limit": 5})

    assert store.calls[0][1] == 5


def test_unknown_file_types_yield_empty_results(store: FakeVectorStore) -> None:
    """全部类型都无法识别 → 空结果，且根本不查向量库。

    mappers 把无法识别的取值丢掉后传空列表，用例把空列表当"限定为空集"。
    """
    store.hits = [make_hit("doc-1", "Q2.pdf", FileType.DOCUMENT)]

    data = build_client(store).post(
        "/search", json={"query": "x", "file_types": ["nonsense"]}
    ).json()["data"]

    assert data == {"documents": [], "images": [], "videos": []}
    assert store.calls == []


def test_vector_store_failure_returns_empty_not_500(store: FakeVectorStore) -> None:
    """检索挂了前端仍要能渲染，所以是 200 + 空结果。"""

    def boom(*_args: object, **_kwargs: object) -> list[VectorHit]:
        raise RuntimeError("chroma 挂了")

    store.search = boom  # type: ignore[method-assign]

    response = build_client(store).post("/search", json={"query": "x"})

    assert response.status_code == 200
    assert response.json()["data"] == {"documents": [], "images": [], "videos": []}


def test_negative_size_filter_is_rejected(client: TestClient) -> None:
    assert client.post("/search", json={"query": "x", "min_size_m": -1}).status_code == 422


def test_zero_limit_is_rejected(client: TestClient) -> None:
    assert client.post("/search", json={"query": "x", "limit": 0}).status_code == 422
