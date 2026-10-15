from __future__ import annotations

import pytest

from fileseek.features.search.application.dto import AgentAssistantMessage
from fileseek.features.search.application.ports import AgentConnection
from fileseek.features.search.domain.exceptions import AgentProviderError
from fileseek.features.settings.application.commands import (
    CreateStorageLocationCommand,
    DeleteStorageLocationCommand,
    ReplaceClassifierLabelsCommand,
    TestAgentSettingsCommand,
    TestStorageConnectionCommand,
    UpdateAgentSettingsCommand,
    UpdateStorageLocationCommand,
)
from fileseek.features.settings.application.dto import AgentSettingsDTO
from fileseek.features.settings.application.queries import ListStorageLocationsQuery
from fileseek.features.settings.application.use_cases import (
    CreateStorageLocationUseCase,
    DeleteStorageLocationUseCase,
    GetAgentSettingsUseCase,
    ListStorageLocationsUseCase,
    ReplaceClassifierLabelsUseCase,
    TestAgentSettingsUseCase,
    TestStorageConnectionUseCase,
    UpdateAgentSettingsUseCase,
    UpdateStorageLocationUseCase,
)
from fileseek.features.settings.domain.entities import (
    AgentSettings,
    ClassifierLabelSet,
    StorageLocation,
)
from fileseek.features.settings.domain.exceptions import StorageConnectionError
from fileseek.shared.domain.exceptions import ValidationError


class FakeClassifierLabelRepository:
    def __init__(self) -> None:
        self.labels = ClassifierLabelSet(
            document_labels=("合同",),
            image_labels=("照片",),
            video_labels=("课程",),
        )

    async def get_label_set(self) -> ClassifierLabelSet:
        return self.labels

    async def replace(self, labels, category: str) -> None:
        _ = labels, category

    async def replace_label_set(self, labels: ClassifierLabelSet) -> None:
        self.labels = labels


class FakeStorageLocationRepository:
    def __init__(self) -> None:
        self.locations = {
            "local": StorageLocation(
                id="local",
                type="local",
                name="本地存储",
                protocol="file",
                endpoint="file://localhost",
                is_system=True,
            ),
            "nas1": StorageLocation(
                id="nas1",
                type="nas",
                name="NAS 1",
                protocol="mounted",
                endpoint="/Volumes/nas1",
                root_path="/Volumes/nas1",
                password="secret",
            ),
        }

    async def get_by_id(
        self,
        location_id: str,
        *,
        include_deleted: bool = False,
    ) -> StorageLocation | None:
        _ = include_deleted
        return self.locations.get(location_id)

    async def list_active_manageable(self) -> list[StorageLocation]:
        return list(self.locations.values())

    async def save(self, location: StorageLocation) -> StorageLocation:
        self.locations[location.id] = location
        return location

    async def mark_deleted(self, location_id: str) -> bool:
        location = self.locations.get(location_id)
        if location is None or location.is_system:
            return False
        self.locations[location_id] = StorageLocation(**{**location.__dict__, "status": "deleted"})
        return True


class FakeAgentSettingsRepository:
    def __init__(self) -> None:
        self.settings: AgentSettings | None = None

    async def get(self) -> AgentSettings | None:
        return self.settings

    async def save(self, settings: AgentSettings) -> AgentSettings:
        self.settings = settings
        return settings


class FakeAgentConnectionTester:
    def __init__(self, response: AgentAssistantMessage | AgentProviderError) -> None:
        self.response = response
        self.connections: list[AgentConnection] = []

    async def test(self, connection: AgentConnection) -> AgentAssistantMessage:
        self.connections.append(connection)
        if isinstance(self.response, AgentProviderError):
            raise self.response
        return self.response


@pytest.mark.asyncio
async def test_get_agent_settings_returns_empty_defaults() -> None:
    use_case = GetAgentSettingsUseCase(FakeAgentSettingsRepository())

    result = await use_case.execute()

    assert result == AgentSettingsDTO(
        base_url="",
        model="",
        api_key_configured=False,
    )


@pytest.mark.asyncio
async def test_update_agent_settings_preserves_key_when_omitted() -> None:
    repository = FakeAgentSettingsRepository()
    repository.settings = AgentSettings(
        base_url="https://api.example.com/v1",
        api_key="secret-key",
        model="old-model",
    )
    use_case = UpdateAgentSettingsUseCase(repository)

    result = await use_case.execute(
        UpdateAgentSettingsCommand(
            base_url="https://api.updated.com/v1",
            model="new-model",
        )
    )

    assert repository.settings is not None
    assert repository.settings.api_key == "secret-key"
    assert result.api_key_configured is True
    assert result.base_url == "https://api.updated.com/v1"


@pytest.mark.asyncio
async def test_update_agent_settings_rejects_invalid_url() -> None:
    repository = FakeAgentSettingsRepository()
    use_case = UpdateAgentSettingsUseCase(repository)

    with pytest.raises(ValidationError) as error:
        await use_case.execute(
            UpdateAgentSettingsCommand(
                base_url="ftp://api.example.com",
                model="retrieval-expert",
                api_key="secret-key",
            )
        )

    assert "http" in str(error.value)
    assert repository.settings is None


@pytest.mark.asyncio
async def test_agent_settings_connection_uses_saved_key_when_omitted() -> None:
    repository = FakeAgentSettingsRepository()
    repository.settings = AgentSettings(
        base_url="https://api.example.com/v1",
        api_key="secret-key",
        model="saved-model",
    )
    tester = FakeAgentConnectionTester(AgentAssistantMessage(content="ok", tool_calls=()))
    use_case = TestAgentSettingsUseCase(
        repository,
        lambda _: tester,
    )

    result = await use_case.execute(
        TestAgentSettingsCommand(
            base_url="https://api.updated.com/v1",
            model="new-model",
        )
    )

    assert result.success is True
    assert result.message == "Agent 连接成功"
    assert tester.connections == [
        AgentConnection(
            base_url="https://api.updated.com/v1",
            api_key="secret-key",
            model="new-model",
        )
    ]


@pytest.mark.asyncio
async def test_agent_settings_connection_reports_provider_failure() -> None:
    repository = FakeAgentSettingsRepository()
    tester = FakeAgentConnectionTester(AgentProviderError("Agent 服务请求失败: HTTP 401"))
    use_case = TestAgentSettingsUseCase(
        repository,
        lambda _: tester,
    )

    result = await use_case.execute(
        TestAgentSettingsCommand(
            base_url="https://api.example.com/v1",
            model="retrieval-expert",
            api_key="secret-key",
        )
    )

    assert result.success is False
    assert result.message == "Agent 服务请求失败: HTTP 401"


@pytest.mark.asyncio
async def test_agent_settings_connection_requires_key() -> None:
    use_case = TestAgentSettingsUseCase(
        FakeAgentSettingsRepository(),
        lambda _: FakeAgentConnectionTester(AgentAssistantMessage(content="ok", tool_calls=())),
    )

    with pytest.raises(ValidationError, match="API Key"):
        await use_case.execute(
            TestAgentSettingsCommand(
                base_url="https://api.example.com/v1",
                model="retrieval-expert",
            )
        )


@pytest.mark.asyncio
async def test_replace_classifier_labels_rejects_duplicates() -> None:
    repository = FakeClassifierLabelRepository()
    use_case = ReplaceClassifierLabelsUseCase(repository)
    original = repository.labels

    with pytest.raises(ValidationError):
        await use_case.execute(
            ReplaceClassifierLabelsCommand(
                document_labels=("合同", "合同"),
                image_labels=(),
                video_labels=(),
            )
        )

    assert repository.labels is original


@pytest.mark.asyncio
async def test_list_storage_locations() -> None:
    repository = FakeStorageLocationRepository()
    use_case = ListStorageLocationsUseCase(repository)

    result = await use_case.execute(ListStorageLocationsQuery())

    assert {location.id for location in result} == {"local", "nas1"}


@pytest.mark.asyncio
async def test_storage_connection_succeeds_for_mounted_path(tmp_path) -> None:
    repository = FakeStorageLocationRepository()
    await repository.save(
        StorageLocation(
            id="nas2",
            type="nas",
            name="NAS 2",
            protocol="mounted",
            endpoint=str(tmp_path),
            root_path=str(tmp_path),
            password="secret",
        )
    )
    use_case = TestStorageConnectionUseCase(repository)

    result = await use_case.execute(TestStorageConnectionCommand(location_id="nas2"))

    assert result.success is True


@pytest.mark.asyncio
async def test_storage_connection_fails_without_exposing_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = FakeStorageLocationRepository()
    await repository.save(
        StorageLocation(
            id="nas2",
            type="nas",
            name="NAS 2",
            protocol="webdav",
            endpoint="webdav://nas.local/media",
            account="user",
            password="secret",
        )
    )

    def fail_connection(address, timeout=None):
        _ = address, timeout
        raise OSError("authentication failed with secret")

    monkeypatch.setattr(
        "fileseek.features.settings.application.use_cases.storage_locations.socket.create_connection",
        fail_connection,
    )
    use_case = TestStorageConnectionUseCase(repository)

    with pytest.raises(StorageConnectionError) as error:
        await use_case.execute(TestStorageConnectionCommand(location_id="nas2"))

    assert "secret" not in str(error.value)


@pytest.mark.asyncio
async def test_create_storage_location_redacts_credentials() -> None:
    repository = FakeStorageLocationRepository()
    use_case = CreateStorageLocationUseCase(repository)

    result = await use_case.execute(
        CreateStorageLocationCommand(
            id="nas2",
            name="NAS 2",
            protocol="mounted",
            endpoint="/Volumes/nas2",
            account="user",
            password="secret",
        )
    )

    assert result.id == "nas2"
    assert not hasattr(result, "password")


@pytest.mark.asyncio
async def test_update_storage_location_preserves_password_when_omitted() -> None:
    repository = FakeStorageLocationRepository()
    use_case = UpdateStorageLocationUseCase(repository)

    await use_case.execute(
        UpdateStorageLocationCommand(
            location_id="nas1",
            name="Updated NAS",
            protocol="mounted",
            endpoint="/Volumes/updated",
        )
    )

    assert repository.locations["nas1"].password == "secret"


@pytest.mark.asyncio
async def test_delete_storage_location_does_not_mark_bound_files() -> None:
    repository = FakeStorageLocationRepository()
    use_case = DeleteStorageLocationUseCase(repository)

    result = await use_case.execute(DeleteStorageLocationCommand(location_id="nas1"))

    assert result.affected_files == 0
    assert repository.locations["nas1"].status == "deleted"


@pytest.mark.asyncio
async def test_delete_local_location_is_rejected() -> None:
    repository = FakeStorageLocationRepository()
    use_case = DeleteStorageLocationUseCase(repository)

    with pytest.raises(ValidationError):
        await use_case.execute(DeleteStorageLocationCommand(location_id="local"))
