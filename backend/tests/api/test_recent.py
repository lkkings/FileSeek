from datetime import UTC, datetime
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from fileseek.features.library.application.dto import FileDTO
from fileseek.features.recent.application.dto import RecentAccessDTO


def test_list_recent_access_paginated(auth_client: TestClient, app):
    mock_use_case = AsyncMock()
    mock_file = FileDTO(
        id="file1",
        name="test.txt",
        file_type="txt",
        category="document",
        size=1024,
        modified=datetime.now(UTC).isoformat(),
        path="/path/test.txt",
        folder_id=None,
        tags=[],
    )
    mock_use_case.execute.return_value = (
        [
            RecentAccessDTO(
                id=1,
                file_id="file1",
                accessed_at="2026-09-28T00:00:00Z",
                file=mock_file,
            ),
        ],
        1,
    )
    app.state.dependencies["list_recent_access_use_case"] = mock_use_case

    response = auth_client.get("/api/v1/recent?page=1&page_size=20")
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["status"] == "success"
    assert json_data["data"]["total"] == 1
    assert len(json_data["data"]["items"]) == 1
    assert json_data["data"]["items"][0]["id"] == 1
    assert json_data["data"]["items"][0]["file_id"] == "file1"
    assert json_data["data"]["items"][0]["file"]["name"] == "test.txt"


def test_record_access_normal(auth_client: TestClient, app):
    mock_use_case = AsyncMock()
    mock_use_case.execute.return_value = None
    app.state.dependencies["record_access_use_case"] = mock_use_case

    payload = {"file_id": "file3"}
    response = auth_client.post("/api/v1/recent", json=payload)
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["status"] == "success"
    assert json_data["data"] is None


def test_delete_recent_access_normal(auth_client: TestClient, app):
    mock_use_case = AsyncMock()
    mock_use_case.execute.return_value = None
    app.state.dependencies["delete_recent_access_use_case"] = mock_use_case

    response = auth_client.delete("/api/v1/recent/42")
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["status"] == "success"
    assert json_data["data"] is None
