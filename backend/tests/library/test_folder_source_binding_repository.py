from __future__ import annotations

from datetime import UTC, datetime

import pytest

from fileseek.config.settings import Settings
from fileseek.features.library.domain.entities import (
    FolderSourceBinding,
    FolderSourceSeen,
)
from fileseek.features.library.infrastructure.repositories import (
    FolderSourceBindingRepositoryImpl,
    FolderSourceSeenRepositoryImpl,
)
from fileseek.infrastructure.database.models import FolderModel, FolderSourceSeenModel


async def create_folder(folder_id: str = "folder-1") -> None:
    await FolderModel.update_or_create(
        id=folder_id,
        defaults={
            "name": "Watched",
            "icon_type": "default",
            "description": "",
            "modified": datetime.now(UTC),
        },
    )


@pytest.mark.asyncio
async def test_folder_source_binding_repository_lifecycle(
    settings: Settings,
) -> None:
    await create_folder()
    repository = FolderSourceBindingRepositoryImpl()
    binding = FolderSourceBinding(
        id="binding-1",
        folder_id="folder-1",
        storage_id="local",
        source_path="/Library/FileSeek/watch",
    )

    await repository.save(binding)
    loaded = await repository.get_by_id("binding-1")

    assert loaded is not None
    assert loaded.id == binding.id
    assert loaded.folder_id == binding.folder_id
    assert loaded.storage_id == binding.storage_id
    assert loaded.source_path == binding.source_path
    assert loaded.recursive is True
    assert loaded.enabled is True
    assert [binding.id] == [item.id for item in await repository.list_by_folder("folder-1")]
    assert [binding.id] == [item.id for item in await repository.list_enabled()]

    loaded.set_enabled(False)
    await repository.save(loaded)
    assert await repository.list_enabled() == []

    await repository.delete("binding-1")
    assert await repository.get_by_id("binding-1") is None


@pytest.mark.asyncio
async def test_folder_source_seen_repository_cascades_with_binding(
    settings: Settings,
) -> None:
    await create_folder()
    binding_repository = FolderSourceBindingRepositoryImpl()
    seen_repository = FolderSourceSeenRepositoryImpl()
    await binding_repository.save(
        FolderSourceBinding(
            id="binding-1",
            folder_id="folder-1",
            storage_id="nas",
            source_path="documents",
        )
    )
    await seen_repository.save(
        FolderSourceSeen(
            id="seen-1",
            binding_id="binding-1",
            source_path="documents/report.pdf",
        )
    )
    await seen_repository.save(
        FolderSourceSeen(
            id="seen-2",
            binding_id="binding-1",
            source_path="documents/report.pdf",
            outcome="imported",
        )
    )

    assert await seen_repository.list_paths("binding-1") == {"documents/report.pdf"}
    record = await FolderSourceSeenModel.get(
        binding_id="binding-1",
        source_path="documents/report.pdf",
    )
    assert record.id == "seen-1"
    assert record.outcome == "imported"

    await binding_repository.delete("binding-1")
    assert await seen_repository.list_paths("binding-1") == set()


@pytest.mark.asyncio
async def test_folder_source_seen_repository_deletes_path(
    settings: Settings,
) -> None:
    await create_folder()
    binding_repository = FolderSourceBindingRepositoryImpl()
    seen_repository = FolderSourceSeenRepositoryImpl()
    await binding_repository.save(
        FolderSourceBinding(
            id="binding-1",
            folder_id="folder-1",
            storage_id="nas",
            source_path="documents",
        )
    )
    await seen_repository.save(
        FolderSourceSeen(
            id="seen-1",
            binding_id="binding-1",
            source_path="documents/report.pdf",
            outcome="imported",
        )
    )

    await seen_repository.delete_path("binding-1", "documents/report.pdf")

    assert await seen_repository.list_paths("binding-1") == set()
