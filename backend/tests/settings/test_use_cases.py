from __future__ import annotations

import pytest

from fileseek.features.settings.application.commands import (
    CreateStorageLocationCommand,
    DeleteStorageLocationCommand,
    ReplaceClassifierLabelsCommand,
    TestStorageConnectionCommand,
    UpdateStorageLocationCommand,
)
from fileseek.features.settings.application.queries import ListStorageLocationsQuery
from fileseek.features.settings.application.use_cases import (
    CreateStorageLocationUseCase,
    DeleteStorageLocationUseCase,
    ListStorageLocationsUseCase,
    ReplaceClassifierLabelsUseCase,
    TestStorageConnectionUseCase,
    UpdateStorageLocationUseCase,
)
from fileseek.features.settings.domain.entities import (
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
        self.locations[location_id] = StorageLocation(
            **{**location.__dict__, "status": "deleted"}
        )
        return True


class FakeFileRepository:
    def __init__(self) -> None:
        self.marked: dict[str, int] = {}

    async def set_access_state(self, file_id: str, access_state: str) -> bool:
        _ = file_id, access_state
        return True

    async def mark_unavailable_by_storage(self, storage_id: str) -> int:
        self.marked[storage_id] = self.marked.get(storage_id, 0) + 1
        return 7


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

    result = await use_case.execute(
        TestStorageConnectionCommand(location_id="nas2")
    )

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
async def test_delete_storage_location_marks_bound_files() -> None:
    repository = FakeStorageLocationRepository()
    file_repository = FakeFileRepository()
    use_case = DeleteStorageLocationUseCase(repository, file_repository)

    result = await use_case.execute(DeleteStorageLocationCommand(location_id="nas1"))

    assert result.affected_files == 7
    assert file_repository.marked == {"nas1": 1}
    assert repository.locations["nas1"].status == "deleted"


@pytest.mark.asyncio
async def test_delete_local_location_is_rejected() -> None:
    repository = FakeStorageLocationRepository()
    file_repository = FakeFileRepository()
    use_case = DeleteStorageLocationUseCase(repository, file_repository)

    with pytest.raises(ValidationError):
        await use_case.execute(DeleteStorageLocationCommand(location_id="local"))
