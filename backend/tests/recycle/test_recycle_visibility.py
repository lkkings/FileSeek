from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from fileseek.config.constant import QUERY_CACHE_KEY
from fileseek.config.settings import Settings
from fileseek.features.library.infrastructure.repositories import FileRepositoryImpl
from fileseek.features.recent.infrastructure.repositories import (
    RecentAccessRepositoryImpl,
)
from fileseek.features.recycle.application.commands import AddFiles2RecycleCommand
from fileseek.features.recycle.application.use_cases.add_files2recycle import (
    AddFiles2RecycleUseCase,
)
from fileseek.infrastructure.database.models import (
    FileModel,
    RecentAccessModel,
    RecycleItemModel,
)
from fileseek.shared.domain.file_types import FileCategory, FileType
from fileseek.shared.domain.identifiers import generate_id
from fileseek.shared.utils.cache import TTLLRUCache


class FakeFileRepository:
    def __init__(self, file: object) -> None:
        self.file = file

    async def get_by_id(self, file_id: str) -> object | None:
        return self.file if file_id == self.file.id else None


class FakeFolderRepository:
    async def increment_file_count(self, folder_id: str, delta: int) -> None:
        return None


class FakeRecycleRepository:
    def __init__(self) -> None:
        self.items: dict[str, object] = {}

    async def save(self, item: object) -> None:
        self.items[item.id] = item


def _recycle_settings(root: Path) -> Settings:
    return Settings(
        lib_root=root,
        db_path=root / "app.db",
        vector_db_path=root / "vectors",
        embedding_model_cache_dir=root / "models",
        recycle_dir=root / "recycle",
        temp_dir=root / "temp",
    )


async def _create_file(file_id: str, path: str) -> None:
    await FileModel.create(
        id=file_id,
        name=f"{file_id}.txt",
        file_type=FileType.TXT.value,
        category=FileCategory.DOCUMENT.value,
        size=1,
        modified=datetime.now(UTC),
        path=path,
        storage_id="local",
        access_state="available",
    )


@pytest.mark.asyncio
async def test_recycled_files_are_excluded_from_recent_access(settings) -> None:
    await _create_file("file-1", str(settings.lib_root / "file-1.txt"))
    await _create_file("file-2", str(settings.lib_root / "file-2.txt"))
    accessed_at = datetime.now(UTC)
    await RecentAccessModel.create(file_id="file-1", accessed_at=accessed_at)
    await RecentAccessModel.create(file_id="file-2", accessed_at=accessed_at)
    await RecycleItemModel.create(
        id="recycle-1",
        file_id="file-1",
        recycle_path=str(settings.lib_root / "recycle-1.zip"),
        deleted_at=datetime.now(UTC),
    )

    records, total = await RecentAccessRepositoryImpl().list_recent_paginated(1, 20)
    recent_ids = await RecentAccessRepositoryImpl().list_recent(20)

    assert total == 1
    assert [record.file_id for record in records] == ["file-2"]
    assert [record.file_id for record in recent_ids] == ["file-2"]


@pytest.mark.asyncio
async def test_recycled_files_are_excluded_from_file_search(settings) -> None:
    await _create_file("file-1", str(settings.lib_root / "file-1.txt"))
    await RecycleItemModel.create(
        id="recycle-1",
        file_id="file-1",
        recycle_path=str(settings.lib_root / "recycle-1.zip"),
        deleted_at=datetime.now(UTC),
    )

    files = await FileRepositoryImpl().query(name_query="file-1")

    assert [file.id for file in files] == []


@pytest.mark.asyncio
async def test_add_files_to_recycle_clears_cached_search_results(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source.txt"
    source.write_text("recycle content", encoding="utf-8")
    cache = TTLLRUCache()
    await cache.set(QUERY_CACHE_KEY, "query", {"items": ["file-1"]})
    monkeypatch.setattr(
        "fileseek.features.recycle.application.use_cases.add_files2recycle.get_settings",
        lambda: _recycle_settings(tmp_path / "library"),
    )

    await AddFiles2RecycleUseCase(
        FakeFileRepository(
            type(
                "File",
                (),
                {
                    "id": generate_id("f"),
                    "name": source.name,
                    "file_type": FileType.TXT,
                    "category": FileCategory.DOCUMENT,
                    "size": source.stat().st_size,
                    "modified": datetime.now(UTC),
                    "path": str(source),
                    "folder_id": None,
                },
            )(),
        ),
        FakeFolderRepository(),
        FakeRecycleRepository(),
        cache,
    ).execute(AddFiles2RecycleCommand(file_ids=["file-1"]))

    assert await cache.get(QUERY_CACHE_KEY, "query") is None
