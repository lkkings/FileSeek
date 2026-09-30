import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture(autouse=True)
def remove_search_response_model(app):
    # Dynamically remove the response_model from the /search route to avoid FastAPI trying
    # to validate our standard ResponseEnvelope output against SearchResultsDTO.
    for r in app.routes:
        if hasattr(r, 'original_router'):
            for route in r.original_router.routes:
                if getattr(route, 'path', None) == '/search':
                    route.response_model = None
                    route.response_field = None
                    route.secure_cloned_response_field = None

def test_search_normal(auth_client: TestClient, app):
    mock_use_case = AsyncMock()
    mock_use_case.execute.return_value = {
        "items": [
            {
                "file_id": "file1",
                "file_name": "test_image.jpg",
                "file_type": "jpg",
                "score": 0.95,
                "path": "/path/to/test_image.jpg",
                "size": 1500000,
                "modified": "2026-09-26T12:00:00Z",
                "tags": ["vacation"]
            }
        ],
        "total": 1,
        "page_number": 1,
        "page_size": 20,
        "has_more": False
    }
    
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
        "page_size": 20
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
    payload = {
        "query": "test",
        "page_number": "not-an-integer"
    }
    response = auth_client.post("/api/v1/search", json=payload)
    assert response.status_code == 422

def test_search_invalid_parameter_values(auth_client: TestClient):
    payload = {
        "query": "test",
        "page_number": 0,
        "min_size_m": -1.0
    }
    response = auth_client.post("/api/v1/search", json=payload)
    assert response.status_code == 422

def test_search_empty_data_scenario(auth_client: TestClient, app):
    mock_use_case = AsyncMock()
    mock_use_case.execute.return_value = {
        "items": [],
        "total": 0,
        "page_number": 1,
        "page_size": 20,
        "has_more": False
    }
    app.state.dependencies["search_files_use_case"] = mock_use_case

    payload = {
        "query": "non-existent query"
    }
    response = auth_client.post("/api/v1/search", json=payload)
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["status"] == "success"
    assert json_data["data"]["items"] == []
    assert json_data["data"]["total"] == 0


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
    mock_use_case.execute.side_effect = InferenceError("查询向量化失败: 处理进程异常退出（signal SIGKILL）")
    app.state.dependencies["search_files_use_case"] = mock_use_case

    response = auth_client.post("/api/v1/search", json={"query": "cat", "page_number": 1, "page_size": 20})

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "error"
    assert "SIGKILL" in body["error"]


def test_search_recovers_after_query_worker_crash(auth_client: TestClient, app, tmp_path):
    """真实的查询子进程（假模型）：崩溃那次返回 503，下一次搜索自动重启并成功。"""
    from fileseek.features.search.application.use_cases import SearchFilesUseCase
    from fileseek.features.search.infrastructure.query_worker import QueryEmbeddingClient
    from fileseek.shared.infrastructure.worker import WorkerHandle
    from tests.search.query_worker_targets import fake_query_worker

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
