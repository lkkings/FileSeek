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


class FakeFolderRepository:
    def __init__(self) -> None:
        self.file_count = 0

    async def get_by_id(self, folder_id: str):
        return None if folder_id == "missing" else object()

    async def increment_file_count(self, folder_id: str, delta: int) -> None:
        _ = folder_id
        self.file_count += delta

    async def save(self, folder) -> None:
        self.file_count = folder.file_count


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
    folder_repository = FakeFolderRepository()
    recycle_repository = FakeRecycleRepository()

    await AddFiles2RecycleUseCase(
        file_repository,
        folder_repository,
        recycle_repository,
        TTLLRUCache(),
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
        folder_repository,
        restore_cache,
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
