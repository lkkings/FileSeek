from __future__ import annotations

import pytest

from fileseek.features.settings.application.commands import (
    DeleteStorageLocationCommand,
    UpdateStorageLocationCommand,
)
from fileseek.features.settings.application.use_cases import (
    DeleteStorageLocationUseCase,
    UpdateStorageLocationUseCase,
)
from fileseek.features.settings.domain.entities import StorageLocation


class FakeStorageRepository:
    def __init__(self, location: StorageLocation) -> None:
        self.location = location

    async def get_by_id(
        self,
        location_id: str,
        *,
        include_deleted: bool = False,
    ) -> StorageLocation:
        return self.location

    async def save(self, location: StorageLocation) -> StorageLocation:
        self.location = location
        return location

    async def mark_deleted(self, location_id: str) -> bool:
        _ = location_id
        return True


class FakeCoordinator:
    def __init__(self) -> None:
        self.reconciled = 0

    async def reconcile(self) -> None:
        self.reconciled += 1


def make_location() -> StorageLocation:
    return StorageLocation(
        id="nas1",
        type="nas",
        name="NAS",
        protocol="mounted",
        endpoint="/Volumes/nas",
        root_path="/Volumes/nas",
    )


@pytest.mark.asyncio
async def test_update_storage_location_reconciles_watchers() -> None:
    coordinator = FakeCoordinator()
    repository = FakeStorageRepository(make_location())
    use_case = UpdateStorageLocationUseCase(repository, coordinator)

    await use_case.execute(
        UpdateStorageLocationCommand(
            location_id="nas1",
            name="NAS",
            protocol="smb",
            endpoint="smb://nas/share",
            root_path="",
        )
    )

    assert coordinator.reconciled == 1


@pytest.mark.asyncio
async def test_delete_storage_location_reconciles_watchers() -> None:
    coordinator = FakeCoordinator()
    repository = FakeStorageRepository(make_location())
    use_case = DeleteStorageLocationUseCase(repository, coordinator)

    result = await use_case.execute(DeleteStorageLocationCommand("nas1"))

    assert result.status == "deleted"
    assert coordinator.reconciled == 1
