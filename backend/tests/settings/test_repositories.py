from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from tempfile import gettempdir

import pytest

from fileseek.config.settings import Settings
from fileseek.features.library.infrastructure.repositories import FileRepositoryImpl
from fileseek.features.settings.application.commands import (
    CreateStorageLocationCommand,
    DeleteStorageLocationCommand,
)
from fileseek.features.settings.application.use_cases import (
    CreateStorageLocationUseCase,
    DeleteStorageLocationUseCase,
)
from fileseek.features.settings.domain.entities import StorageLocation
from fileseek.features.settings.infrastructure import (
    TortoiseClassifierLabelRepository,
    TortoiseStorageLocationRepository,
)
from fileseek.infrastructure.database import connection
from fileseek.infrastructure.database.models import FileModel, TagModel
from fileseek.shared.domain.file_types import FileCategory, FileType

test_path = str(Path(gettempdir()) / "file.txt")


@pytest.mark.asyncio
async def test_storage_location_repository_lifecycle(settings: Settings) -> None:
    repository = TortoiseStorageLocationRepository()
    location = StorageLocation(
        id="nas1",
        type="nas",
        name="NAS 存储 1",
        protocol="mounted",
        endpoint="/Volumes/nas1",
        root_path="/Volumes/nas1",
        account="user",
        password="secret",
    )

    saved = await repository.save(location)
    active = await repository.list_active_manageable()

    assert saved.id == "nas1"
    assert {item.id for item in active} == {"local", "nas1"}

    updated = await repository.save(
        StorageLocation(
            **{
                **location.__dict__,
                "name": "Updated NAS",
                "endpoint": "/Volumes/updated",
            }
        )
    )
    assert updated.name == "Updated NAS"

    assert await repository.mark_deleted("nas1") is True
    assert await repository.get_by_id("nas1") is None
    deleted = await repository.get_by_id("nas1", include_deleted=True)
    assert deleted is not None
    assert deleted.status == "deleted"


@pytest.mark.asyncio
async def test_classifier_label_repository_replaces_vocabulary(
    settings: Settings,
) -> None:
    repository = TortoiseClassifierLabelRepository()
    initial = await repository.get_label_set()

    await repository.replace(["合同", "发票"], "document")
    updated = await repository.get_label_set()

    assert initial.version != updated.version
    assert updated.document_labels == ("发票", "合同")
    assert updated.image_labels == initial.image_labels


@pytest.mark.asyncio
async def test_default_seed_is_idempotent(
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = TortoiseClassifierLabelRepository()
    await repository.replace(["用户标签"], "document")
    updated = await repository.get_label_set()

    await connection.close_db()
    monkeypatch.setattr(connection, "get_settings", lambda: settings)
    await connection.init_db()
    reloaded = await repository.get_label_set()

    assert reloaded.document_labels == ("用户标签",)
    assert reloaded.version == updated.version


@pytest.mark.asyncio
async def test_delete_storage_location_retains_file_indexes(
    settings: Settings,
) -> None:
    storage_repository = TortoiseStorageLocationRepository()
    file_repository = FileRepositoryImpl()
    create_use_case = CreateStorageLocationUseCase(storage_repository)
    delete_use_case = DeleteStorageLocationUseCase(
        storage_repository,
        file_repository,
    )
    await create_use_case.execute(
        CreateStorageLocationCommand(
            id="nas1",
            name="NAS 1",
            protocol="mounted",
            endpoint="/Volumes/nas1",
            root_path="/Volumes/nas1",
        )
    )
    await FileModel.create(
        id="file-1",
        name="file.txt",
        file_type=FileType.TXT.value,
        category=FileCategory.DOCUMENT.value,
        size=1,
        modified=datetime.now(UTC),
        path="/Volumes/nas1/file.txt",
        storage_id="nas1",
        access_state="available",
    )

    result = await delete_use_case.execute(
        DeleteStorageLocationCommand(location_id="nas1")
    )
    model = await FileModel.get(id="file-1")

    assert result.affected_files == 1
    assert model.storage_id == "nas1"
    assert model.access_state == "unavailable"
    assert model.path == "/Volumes/nas1/file.txt"


@pytest.mark.asyncio
async def test_classifier_label_replacement_keeps_file_tags(
    settings: Settings,
) -> None:
    tag = await TagModel.create(id="tag-1", name="合同")
    file_model = await FileModel.create(
        id="file-1",
        name="file.txt",
        file_type=FileType.TXT.value,
        category=FileCategory.DOCUMENT.value,
        size=1,
        modified=datetime.now(UTC),
        path=test_path,
        storage_id="local",
        access_state="available",
    )
    await file_model.tags.add(tag)
    repository = TortoiseClassifierLabelRepository()

    await repository.replace([], "document")
    await file_model.fetch_related("tags")

    assert [item.name for item in file_model.tags] == ["合同"]
