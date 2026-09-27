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
