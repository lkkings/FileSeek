from datetime import datetime
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from fileseek.features.settings.application.commands import TestAgentSettingsCommand
from fileseek.features.settings.application.dto import (
    AgentSettingsDTO,
    ClassifierLabelsDTO,
    ConnectionTestResultDTO,
    StorageDirectoryDTO,
    StorageDirectoryEntryDTO,
    StorageLocationDeletionDTO,
    StorageLocationDTO,
)
from fileseek.features.settings.application.queries import ListStorageDirectoryQuery
from fileseek.features.settings.domain.exceptions import (
    StorageBrowseUnavailableError,
)
from fileseek.shared.domain.exceptions import ValidationError


def test_get_agent_settings_incomplete(auth_client: TestClient, app) -> None:
    use_case = AsyncMock()
    use_case.execute.return_value = AgentSettingsDTO(
        base_url="https://api.example.com/v1",
        model="retrieval-expert",
        api_key_configured=False,
    )
    app.state.dependencies["get_agent_settings_use_case"] = use_case

    response = auth_client.get("/api/v1/settings/agent")

    assert response.status_code == 200
    assert response.json()["data"] == {
        "base_url": "https://api.example.com/v1",
        "model": "retrieval-expert",
        "api_key_configured": False,
    }


def test_update_agent_settings_masks_key(auth_client: TestClient, app) -> None:
    use_case = AsyncMock()
    use_case.execute.return_value = AgentSettingsDTO(
        base_url="https://api.example.com/v1",
        model="retrieval-expert",
        api_key_configured=True,
    )
    app.state.dependencies["update_agent_settings_use_case"] = use_case

    response = auth_client.put(
        "/api/v1/settings/agent",
        json={
            "base_url": "https://api.example.com/v1",
            "model": "retrieval-expert",
            "api_key": "secret-key",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["api_key_configured"] is True
    assert "secret-key" not in body
    assert use_case.execute.await_count == 1


def test_update_agent_settings_rejects_invalid_url(
    auth_client: TestClient,
    app,
) -> None:
    use_case = AsyncMock()
    use_case.execute.side_effect = ValidationError("Agent 地址必须是 http 或 https URL")
    app.state.dependencies["update_agent_settings_use_case"] = use_case

    response = auth_client.put(
        "/api/v1/settings/agent",
        json={
            "base_url": "ftp://api.example.com",
            "model": "retrieval-expert",
            "api_key": "secret-key",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "error"
    assert "http" in body["error"]
    assert "secret-key" not in body["error"]


def test_agent_settings_connection_test(auth_client: TestClient, app) -> None:
    use_case = AsyncMock()
    use_case.execute.return_value = ConnectionTestResultDTO(
        success=False,
        message="Agent 服务请求失败: HTTP 401",
    )
    app.state.dependencies["test_agent_settings_use_case"] = use_case

    response = auth_client.post(
        "/api/v1/settings/agent/test",
        json={
            "base_url": "https://api.example.com/v1",
            "model": "retrieval-expert",
            "api_key": "secret-key",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["data"] == {
        "success": False,
        "message": "Agent 服务请求失败: HTTP 401",
    }
    assert "secret-key" not in body
    command = use_case.execute.await_args.args[0]
    assert command == TestAgentSettingsCommand(
        base_url="https://api.example.com/v1",
        model="retrieval-expert",
        api_key="secret-key",
    )


def test_get_classifier_labels(auth_client: TestClient, app) -> None:
    use_case = AsyncMock()
    use_case.execute.return_value = ClassifierLabelsDTO(
        document_labels=("合同",),
        image_labels=("照片",),
        video_labels=("课程",),
        version="version-1",
    )
    app.state.dependencies["get_classifier_labels_use_case"] = use_case

    response = auth_client.get("/api/v1/settings/classifier-labels")

    assert response.status_code == 200
    assert response.json()["data"] == {
        "document_labels": ["合同"],
        "image_labels": ["照片"],
        "video_labels": ["课程"],
        "version": "version-1",
    }


def test_replace_classifier_labels_error(auth_client: TestClient, app) -> None:
    use_case = AsyncMock()
    use_case.execute.side_effect = ValidationError("document 标签存在重复")
    app.state.dependencies["replace_classifier_labels_use_case"] = use_case

    response = auth_client.put(
        "/api/v1/settings/classifier-labels",
        json={
            "document_labels": ["合同", "合同"],
            "image_labels": [],
            "video_labels": [],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "error"
    assert body["data"] is None
    assert "重复" in body["error"]


def test_list_storage_locations(auth_client: TestClient, app) -> None:
    use_case = AsyncMock()
    use_case.execute.return_value = [
        StorageLocationDTO(
            id="local",
            type="local",
            name="本地存储",
            protocol="file",
            endpoint="file://localhost",
            root_path="/library",
            account=None,
            status="active",
            is_system=True,
        ),
        StorageLocationDTO(
            id="nas1",
            type="nas",
            name="NAS 1",
            protocol="mounted",
            endpoint="/Volumes/nas1",
            root_path="/Volumes/nas1",
            account="user",
            status="active",
            is_system=False,
        ),
    ]
    app.state.dependencies["list_storage_locations_use_case"] = use_case

    response = auth_client.get("/api/v1/settings/storage-locations")

    assert response.status_code == 200
    data = response.json()["data"]
    assert {location["id"] for location in data} == {"local", "nas1"}
    assert all("password" not in location for location in data)


def test_list_storage_directory(auth_client: TestClient, app) -> None:
    use_case = AsyncMock()
    use_case.execute.return_value = StorageDirectoryDTO(
        current_path="Documents",
        entries=(
            StorageDirectoryEntryDTO(
                name="Documents",
                kind="directory",
                source_path="Documents",
                size=0,
                modified=datetime(2026, 9, 29, 10, 0, 0),
            ),
            StorageDirectoryEntryDTO(
                name="report.pdf",
                kind="file",
                source_path="Documents/report.pdf",
                size=2048,
                modified=datetime(2026, 9, 29, 11, 0, 0),
            ),
        ),
    )
    app.state.dependencies["list_storage_directory_use_case"] = use_case

    response = auth_client.get(
        "/api/v1/settings/storage-locations/nas1/directory",
        params={"path": "Documents"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["current_path"] == "Documents"
    assert response.json()["data"]["entries"][0]["source_path"] == "Documents"
    use_case.execute.assert_awaited_once_with(
        ListStorageDirectoryQuery(storage_id="nas1", path="Documents")
    )


def test_list_storage_directory_missing(auth_client: TestClient, app) -> None:
    use_case = AsyncMock()
    use_case.execute.side_effect = StorageBrowseUnavailableError("目录不可访问")
    app.state.dependencies["list_storage_directory_use_case"] = use_case

    response = auth_client.get(
        "/api/v1/settings/storage-locations/nas1/directory",
        params={"path": "missing"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "error"


def test_create_storage_location(auth_client: TestClient, app) -> None:
    use_case = AsyncMock()
    use_case.execute.return_value = StorageLocationDTO(
        id="nas1",
        type="nas",
        name="NAS 1",
        protocol="mounted",
        endpoint="/Volumes/nas1",
        root_path="/Volumes/nas1",
        account="user",
        status="active",
        is_system=False,
    )
    app.state.dependencies["create_storage_location_use_case"] = use_case

    response = auth_client.post(
        "/api/v1/settings/storage-locations",
        json={
            "id": "nas1",
            "name": "NAS 1",
            "protocol": "mounted",
            "endpoint": "/Volumes/nas1",
            "root_path": "/Volumes/nas1",
            "account": "user",
            "password": "secret",
        },
    )

    assert response.status_code == 200
    assert "password" not in response.json()["data"]


def test_update_storage_location(auth_client: TestClient, app) -> None:
    use_case = AsyncMock()
    use_case.execute.return_value = StorageLocationDTO(
        id="nas1",
        type="nas",
        name="Updated",
        protocol="mounted",
        endpoint="/Volumes/updated",
        root_path="/Volumes/updated",
        account="user",
        status="active",
        is_system=False,
    )
    app.state.dependencies["update_storage_location_use_case"] = use_case

    response = auth_client.put(
        "/api/v1/settings/storage-locations/nas1",
        json={
            "name": "Updated",
            "protocol": "mounted",
            "endpoint": "/Volumes/updated",
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["name"] == "Updated"


def test_delete_storage_location(auth_client: TestClient, app) -> None:
    use_case = AsyncMock()
    use_case.execute.return_value = StorageLocationDeletionDTO(
        id="nas1",
        status="deleted",
        affected_files=3,
    )
    app.state.dependencies["delete_storage_location_use_case"] = use_case

    response = auth_client.delete("/api/v1/settings/storage-locations/nas1")

    assert response.status_code == 200
    assert response.json()["data"] == {
        "id": "nas1",
        "status": "deleted",
        "affected_files": 3,
    }


def test_storage_connection(auth_client: TestClient, app) -> None:
    use_case = AsyncMock()
    use_case.execute.return_value = ConnectionTestResultDTO(
        success=True,
        message="连接成功",
    )
    app.state.dependencies["test_storage_connection_use_case"] = use_case

    response = auth_client.post("/api/v1/settings/storage-locations/nas1/test")

    assert response.status_code == 200
    assert response.json()["data"] == {"success": True, "message": "连接成功"}
