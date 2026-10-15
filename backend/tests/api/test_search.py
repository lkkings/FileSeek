import asyncio
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from fileseek.features.search.application.dto import (
    EnhancedSearchProgressDTO,
    FileDTO,
    SearchResultsDTO,
)
from fileseek.features.search.domain.exceptions import AgentProviderError
from fileseek.features.search.interfaces.http import routers as search_routes
from fileseek.shared.domain.exceptions import ValidationError


def enhanced_result() -> SearchResultsDTO:
    return SearchResultsDTO(
        items=[
            FileDTO(
                file_id="file1",
                file_name="cat.jpg",
                file_type="jpg",
                category="image",
                path="/library/cat.jpg",
                size=100,
                modified="2026-10-01T00:00:00",
                tags=["travel"],
                score=0.9,
            )
        ],
        counter={"document": 0, "image": 1, "video": 0},
        total=1,
        page_number=1,
        page_size=20,
    )


def search_result() -> SearchResultsDTO:
    return SearchResultsDTO(
        items=[
            FileDTO(
                file_id="file1",
                file_name="test_image.jpg",
                file_type="jpg",
                category="image",
                path="/path/to/test_image.jpg",
                size=1_500_000,
                modified="2026-09-26T12:00:00Z",
                tags=["vacation"],
                score=0.95,
            )
        ],
        counter={"document": 0, "image": 1, "video": 0},
        total=1,
        page_number=1,
        page_size=20,
    )


@pytest.fixture(autouse=True)
def remove_search_response_model(app):
    # Dynamically remove the response_model from the /search route to avoid FastAPI trying
    # to validate our standard ResponseEnvelope output against SearchResultsDTO.
    for r in app.routes:
        if hasattr(r, "original_router"):
            for route in r.original_router.routes:
                if getattr(route, "path", None) == "/search":
                    route.response_model = None
                    route.response_field = None
                    route.secure_cloned_response_field = None


def test_search_normal(auth_client: TestClient, app):
    mock_use_case = AsyncMock()
    mock_use_case.execute.return_value = search_result()

    app.state.dependencies["search_files_use_case"] = mock_use_case

    payload = {
        "query": "find some images",
        "folder_id": "folder1",
        "categories": ["image"],
        "tag": "vacation",
        "name_query": "test",
        "min_size_m": 1.0,
        "max_size_m": 5.0,
        "start_date": "2026-09-01",
        "end_date": "2026-09-30",
        "page_number": 1,
        "page_size": 20,
    }

    response = auth_client.post("/api/v1/search", json=payload)
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["status"] == "success"
    assert len(json_data["data"]["items"]) == 1
    assert json_data["data"]["items"][0]["file_id"] == "file1"
    assert json_data["data"]["items"][0]["file_name"] == "test_image.jpg"
    assert json_data["data"]["total"] == 1


def test_search_missing_token(client: TestClient):
    response = client.post("/api/v1/search", json={"query": "test"})
    assert response.status_code == 401


def test_search_invalid_token(client: TestClient):
    client.headers.update({"X-FileSeek-Token": "wrong-token"})
    response = client.post("/api/v1/search", json={"query": "test"})
    assert response.status_code == 401


def test_search_missing_required_params(auth_client: TestClient):
    # 'query' is required based on SearchRequest schema: query: str = Field(...)
    response = auth_client.post("/api/v1/search", json={})
    assert response.status_code == 422
    json_data = response.json()
    assert json_data["status"] == "error"
    assert "请求参数不合法" in json_data["error"]


def test_search_invalid_parameter_types(auth_client: TestClient):
    payload = {"query": "test", "page_number": "not-an-integer"}
    response = auth_client.post("/api/v1/search", json=payload)
    assert response.status_code == 422


def test_search_invalid_parameter_values(auth_client: TestClient):
    payload = {"query": "test", "page_number": 0, "min_size_m": -1.0}
    response = auth_client.post("/api/v1/search", json=payload)
    assert response.status_code == 422


def test_search_empty_data_scenario(auth_client: TestClient, app):
    mock_use_case = AsyncMock()
    mock_use_case.execute.return_value = SearchResultsDTO(
        items=[],
        counter={"document": 0, "image": 0, "video": 0},
        total=0,
        page_number=1,
        page_size=20,
    )
    app.state.dependencies["search_files_use_case"] = mock_use_case

    payload = {"query": "non-existent query"}
    response = auth_client.post("/api/v1/search", json=payload)
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["status"] == "success"
    assert json_data["data"]["items"] == []
    assert json_data["data"]["total"] == 0


def test_enhanced_search_success(auth_client: TestClient, app):
    use_case = AsyncMock()
    use_case.execute.return_value = enhanced_result()
    app.state.dependencies["enhanced_search_use_case"] = use_case

    response = auth_client.post(
        "/api/v1/search/enhanced",
        json={"query": "上个月旅行的猫照片", "page_number": 1, "page_size": 20},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["data"]["items"][0]["file_id"] == "file1"
    assert body["data"]["total"] == 1
    assert body["data"]["counter"]["image"] == 1
    assert body["data"]["has_more"] is False
    assert use_case.execute.await_count == 1


def test_enhanced_search_empty_result(auth_client: TestClient, app):
    use_case = AsyncMock()
    use_case.execute.return_value = SearchResultsDTO(
        items=[],
        counter={"document": 0, "image": 0, "video": 0},
        total=0,
        page_number=1,
        page_size=20,
    )
    app.state.dependencies["enhanced_search_use_case"] = use_case

    response = auth_client.post("/api/v1/search/enhanced", json={"query": "不存在"})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["data"]["items"] == []
    assert body["data"]["total"] == 0


def test_enhanced_search_missing_settings(auth_client: TestClient, app):
    use_case = AsyncMock()
    use_case.execute.side_effect = ValidationError("检索智能体未配置，请先完成系统设置")
    app.state.dependencies["enhanced_search_use_case"] = use_case

    response = auth_client.post("/api/v1/search/enhanced", json={"query": "猫照片"})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "error"
    assert "未配置" in body["error"]


def test_enhanced_search_provider_failure(auth_client: TestClient, app):
    use_case = AsyncMock()
    use_case.execute.side_effect = AgentProviderError("Agent 请求超时")
    app.state.dependencies["enhanced_search_use_case"] = use_case

    response = auth_client.post("/api/v1/search/enhanced", json={"query": "猫照片"})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "error"
    assert body["error"] == "Agent 请求超时"


class StreamUseCase:
    def __init__(self, events: list[EnhancedSearchProgressDTO]) -> None:
        self.events = events

    async def execute_stream(self, query):
        for event in self.events:
            yield event


class SlowStreamUseCase:
    async def execute_stream(self, query):
        yield EnhancedSearchProgressDTO(type="status", phase="starting")
        await asyncio.sleep(0.05)
        yield EnhancedSearchProgressDTO(type="result", result=enhanced_result())


def test_enhanced_search_stream_emits_progress_and_result(auth_client: TestClient, app):
    app.state.dependencies["enhanced_search_use_case"] = StreamUseCase(
        [
            EnhancedSearchProgressDTO(type="status", phase="starting"),
            EnhancedSearchProgressDTO(
                type="tool_call",
                round_number=1,
                tool_name="search_files",
                query="猫照片",
                categories=("image",),
            ),
            EnhancedSearchProgressDTO(
                type="tool_result",
                round_number=1,
                tool_name="search_files",
                candidate_count=1,
                total=1,
            ),
            EnhancedSearchProgressDTO(type="result", result=enhanced_result()),
        ]
    )

    response = auth_client.post(
        "/api/v1/search/enhanced/stream",
        json={"query": "上个月旅行的猫照片"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache"
    assert response.text.count("event: progress\n") == 4
    assert '"type":"status"' in response.text
    assert '"type":"tool_call"' in response.text
    assert '"type":"tool_result"' in response.text
    assert '"type":"result"' in response.text
    assert '"file_id":"file1"' in response.text


def test_enhanced_search_stream_reports_cache_hit(auth_client: TestClient, app):
    app.state.dependencies["enhanced_search_use_case"] = StreamUseCase(
        [
            EnhancedSearchProgressDTO(type="status", phase="cache_hit"),
            EnhancedSearchProgressDTO(type="result", result=enhanced_result()),
        ]
    )

    response = auth_client.post("/api/v1/search/enhanced/stream", json={"query": "猫照片"})

    assert response.status_code == 200
    assert '"phase":"cache_hit"' in response.text
    assert response.text.count("event: progress\n") == 2


def test_enhanced_search_stream_ends_with_error(auth_client: TestClient, app):
    app.state.dependencies["enhanced_search_use_case"] = StreamUseCase(
        [
            EnhancedSearchProgressDTO(type="status", phase="starting"),
            EnhancedSearchProgressDTO(type="error", error="Agent 请求超时"),
        ]
    )

    response = auth_client.post("/api/v1/search/enhanced/stream", json={"query": "猫照片"})

    assert response.status_code == 200
    assert '"type":"error"' in response.text
    assert '"error":"Agent 请求超时"' in response.text
    assert response.text.count("event: progress\n") == 2


def test_enhanced_search_stream_keepalive_does_not_cancel_pending_work(
    auth_client: TestClient,
    app,
    monkeypatch,
):
    monkeypatch.setattr(search_routes, "PROGRESS_KEEPALIVE_SECONDS", 0.01)
    app.state.dependencies["enhanced_search_use_case"] = SlowStreamUseCase()

    response = auth_client.post(
        "/api/v1/search/enhanced/stream",
        json={"query": "猫照片"},
    )

    assert response.status_code == 200
    assert ": ping" in response.text
    assert '"type":"result"' in response.text
    assert '"file_id":"file1"' in response.text


class _FakeQueryClient:
    def __init__(self) -> None:
        self.running = False
        self.calls = 0

    def ensure_started(self) -> bool:
        self.calls += 1
        if self.running:
            return False
        self.running = True
        return True


def test_warmup_returns_202_and_starts_once(auth_client: TestClient, app):
    fake = _FakeQueryClient()
    app.state.dependencies["query_embedding_client"] = fake

    first = auth_client.post("/api/v1/search/warmup")
    second = auth_client.post("/api/v1/search/warmup")

    assert first.status_code == 202
    assert first.json()["data"] == {"started": True}
    assert second.status_code == 202
    assert second.json()["data"] == {"started": False}
    assert fake.calls == 2


def test_warmup_requires_token(client: TestClient, app):
    app.state.dependencies["query_embedding_client"] = _FakeQueryClient()

    response = client.post("/api/v1/search/warmup")

    assert response.status_code == 401


def test_search_returns_503_when_query_model_unavailable(auth_client: TestClient, app):
    from fileseek.shared.domain.exceptions import InferenceError

    mock_use_case = AsyncMock()
    mock_use_case.execute.side_effect = InferenceError(
        "查询向量化失败: 处理进程异常退出（signal SIGKILL）"
    )
    app.state.dependencies["search_files_use_case"] = mock_use_case

    response = auth_client.post(
        "/api/v1/search", json={"query": "cat", "page_number": 1, "page_size": 20}
    )

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "error"
    assert "SIGKILL" in body["error"]


def test_search_recovers_after_query_worker_crash(auth_client: TestClient, app, tmp_path):
    """真实的查询子进程（假模型）：崩溃那次返回 503，下一次搜索自动重启并成功。"""
    from tests.search.query_worker_targets import fake_query_worker

    from fileseek.features.search.application.use_cases import SearchFilesUseCase
    from fileseek.features.search.infrastructure.query_worker import QueryEmbeddingClient
    from fileseek.shared.infrastructure.worker import WorkerHandle

    client = QueryEmbeddingClient(
        WorkerHandle("test-query-worker", fake_query_worker, {"idle_timeout": 0})
    )

    class _EmptyVectors:
        def query(self, *args, **kwargs):
            return []

        def __getattr__(self, name):
            return lambda *args, **kwargs: []

    class _Files:
        """空文件库：所有查询都返回空、计数都为 0。"""

        def __getattr__(self, name):
            async def _empty(*args, **kwargs):
                return {} if name.startswith("count") else []

            return _empty

    class _Cache:
        async def get(self, *args):
            return None

        async def set(self, *args):
            return None

    use_case = SearchFilesUseCase(client, _EmptyVectors(), _Files(), _Cache())
    app.state.dependencies["search_files_use_case"] = use_case
    payload = {"query": "cat", "page_number": 1, "page_size": 20}
    try:
        # 让子进程在处理下一条查询时自杀
        payload_crash = {**payload, "query": "crash"}
        crashed = auth_client.post("/api/v1/search", json=payload_crash)
        recovered = auth_client.post("/api/v1/search", json=payload)
    finally:
        client.shutdown()

    assert crashed.status_code == 503
    assert recovered.status_code == 200, recovered.text
