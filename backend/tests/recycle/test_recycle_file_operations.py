from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from zipfile import ZipFile

import pytest

from fileseek.config.constant import QUERY_CACHE_KEY
from fileseek.config.settings import Settings
from fileseek.features.library.domain.entities import File
from fileseek.features.recycle.application.commands import (
    AddFiles2RecycleCommand,
    DeletePermanentlyCommand,
    RestoreItemsCommand,
)
from fileseek.features.recycle.application.use_cases.add_files2recycle import (
    AddFiles2RecycleUseCase,
)
from fileseek.features.recycle.application.use_cases.delete_recycle_bin import (
    DeleteRecycleUseCase,
)
from fileseek.features.recycle.application.use_cases.restore_recycle import (
    RestoreRecycleUseCase,
)
from fileseek.features.recycle.domain.entities import RecycleItem
from fileseek.features.settings.domain.entities import StorageLocation
from fileseek.features.settings.infrastructure import StorageSourceResolver
from fileseek.features.settings.infrastructure.source_access import LocalSourceFile
from fileseek.shared.domain.file_types import FileCategory, FileType
from fileseek.shared.utils.cache import TTLLRUCache


class FakeFileRepository:
    def __init__(self, file: File | None = None) -> None:
        self.file = file
        self.deleted: list[str] = []

    async def get_by_id(self, file_id: str) -> File | None:
        return self.file if file_id == self.file.id else None

    async def delete_batch(self, file_ids: list[str]) -> int:
        self.deleted.extend(file_ids)
        return len(file_ids)


class FakeRecycleRepository:
    def __init__(self) -> None:
        self.items: dict[str, RecycleItem] = {}

    async def get_by_id(self, item_id: str) -> RecycleItem | None:
        return self.items.get(item_id)

    async def save(self, item: RecycleItem) -> None:
        self.items[item.id] = item

    async def delete(self, item_id: str) -> None:
        self.items.pop(item_id, None)


class FakeVectorIndex:
    def __init__(self) -> None:
        self.deleted_ids: list[str] = []

    def delete_batch(self, chunk_ids: list[str]) -> None:
        self.deleted_ids.extend(chunk_ids)


class FakeStorageLocationRepository:
    def __init__(self, location: StorageLocation) -> None:
        self.location = location

    async def get_by_id(
        self,
        location_id: str,
        *,
        include_deleted: bool = False,
    ) -> StorageLocation | None:
        _ = include_deleted
        return self.location if location_id == self.location.id else None


class FakeSourceResolver:
    async def resolve(self, storage_id: str, source_path: str):
        _ = storage_id
        return LocalSourceFile(Path(source_path))


def _settings(root: Path) -> Settings:
    return Settings(
        lib_root=root,
        db_path=root / "app.db",
        vector_db_path=root / "vectors",
        embedding_model_cache_dir=root / "models",
        recycle_dir=root / "recycle",
        temp_dir=root / "temp",
    )


def _file(path: Path) -> File:
    return File(
        id="file-1",
        name=path.name,
        file_type=FileType.TXT,
        category=FileCategory.DOCUMENT,
        size=path.stat().st_size,
        modified=datetime.now(UTC),
        path=str(path),
        folder_id=None,
        storage_id="local",
        access_state="available",
        tags=[],
    )


@pytest.mark.asyncio
async def test_recycle_compresses_restores_and_permanently_deletes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source.txt"
    source.write_text("recycle content", encoding="utf-8")
    file = _file(source)
    settings = _settings(tmp_path / "library")
    monkeypatch.setattr(
        "fileseek.features.recycle.application.use_cases.add_files2recycle.get_settings",
        lambda: settings,
    )
    file_repository = FakeFileRepository(file)
    recycle_repository = FakeRecycleRepository()

    await AddFiles2RecycleUseCase(
        file_repository,
        recycle_repository,
        TTLLRUCache(),
        FakeSourceResolver(),
    ).execute(AddFiles2RecycleCommand(file_ids=["file-1"]))

    item = next(iter(recycle_repository.items.values()))
    assert not source.exists()
    assert Path(item.recycle_path or "").exists()
    with ZipFile(item.recycle_path or "") as archive:
        assert archive.namelist() == ["source.txt"]

    restore_cache = TTLLRUCache()
    await restore_cache.set(QUERY_CACHE_KEY, "query", {"items": ["file-1"]})
    await RestoreRecycleUseCase(
        recycle_repository,
        file_repository,
        restore_cache,
        FakeSourceResolver(),
    ).execute(RestoreItemsCommand(item_ids=[item.id]))
    assert await restore_cache.get(QUERY_CACHE_KEY, "query") is None

    assert source.read_text(encoding="utf-8") == "recycle content"
    assert not Path(item.recycle_path or "").exists()
    assert item.id not in recycle_repository.items

    source.unlink()
    Path(item.recycle_path or "").write_bytes(b"archive")
    recycle_repository.items[item.id] = item
    vector_index = FakeVectorIndex()

    await DeleteRecycleUseCase(
        recycle_repository,
        file_repository,
        vector_index,
    ).execute(DeletePermanentlyCommand(item_ids=[item.id]))

    assert not Path(item.recycle_path or "").exists()
    assert file_repository.deleted == ["file-1"]
    assert item.id not in recycle_repository.items


@pytest.mark.asyncio
async def test_recycle_resolves_and_restores_mounted_nas_relative_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    nas_root = tmp_path / "nas"
    source = nas_root / "source.txt"
    source.parent.mkdir()
    source.write_text("nas recycle content", encoding="utf-8")
    file = _file(source)
    file.path = "source.txt"
    file.storage_id = "nas1"
    monkeypatch.setattr(
        "fileseek.features.recycle.application.use_cases.add_files2recycle.get_settings",
        lambda: _settings(tmp_path / "library"),
    )
    resolver = StorageSourceResolver(
        FakeStorageLocationRepository(
            StorageLocation(
                id="nas1",
                type="nas",
                name="NAS 1",
                protocol="mounted",
                endpoint=str(nas_root),
                root_path=str(nas_root),
            )
        )
    )
    recycle_repository = FakeRecycleRepository()

    await AddFiles2RecycleUseCase(
        FakeFileRepository(file),
        recycle_repository,
        TTLLRUCache(),
        resolver,
    ).execute(AddFiles2RecycleCommand(file_ids=["file-1"]))

    item = next(iter(recycle_repository.items.values()))
    assert not source.exists()

    await RestoreRecycleUseCase(
        recycle_repository,
        FakeFileRepository(file),
        TTLLRUCache(),
        resolver,
    ).execute(RestoreItemsCommand(item_ids=[item.id]))

    assert source.read_text(encoding="utf-8") == "nas recycle content"


@pytest.mark.asyncio
async def test_recycle_infers_storage_for_legacy_local_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "legacy.txt"
    source.write_text("legacy recycle content", encoding="utf-8")
    file = _file(source)
    file.storage_id = None
    monkeypatch.setattr(
        "fileseek.features.recycle.application.use_cases.add_files2recycle.get_settings",
        lambda: _settings(tmp_path / "library"),
    )
    resolver = StorageSourceResolver(
        FakeStorageLocationRepository(
            StorageLocation(
                id="local",
                type="local",
                name="本地存储",
                protocol="file",
                endpoint="file://localhost",
                root_path=str(tmp_path),
            )
        )
    )
    recycle_repository = FakeRecycleRepository()

    await AddFiles2RecycleUseCase(
        FakeFileRepository(file),
        recycle_repository,
        TTLLRUCache(),
        resolver,
    ).execute(AddFiles2RecycleCommand(file_ids=["file-1"]))

    item = next(iter(recycle_repository.items.values()))
    assert item.storage_id == "local"
    assert not source.exists()

    await RestoreRecycleUseCase(
        recycle_repository,
        FakeFileRepository(file),
        TTLLRUCache(),
        resolver,
    ).execute(RestoreItemsCommand(item_ids=[item.id]))

    assert source.read_text(encoding="utf-8") == "legacy recycle content"
