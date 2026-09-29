from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from fileseek.features.library.infrastructure.repositories import folder as folder_module
from fileseek.features.library.infrastructure.repositories.folder import (
    FolderRepositoryImpl,
)


class FakeFolderModel:
    model = SimpleNamespace(
        id="folder-1",
        name="Documents",
        icon_type="document",
        description="",
        modified="2026-09-29T00:00:00Z",
    )

    @classmethod
    async def get_or_none(cls, **filters: Any) -> Any:
        assert filters == {"id": "folder-1"}
        return cls.model


class FakeFileQuery:
    def __init__(self, active_file_count: int) -> None:
        self.active_file_count = active_file_count
        self.filters: dict[str, Any] = {}

    def filter(self, **filters: Any) -> FakeFileQuery:
        self.filters = filters
        return self

    async def count(self) -> int:
        assert self.filters == {
            "folder_id": "folder-1",
            "recycle_item__isnull": True,
        }
        return self.active_file_count


class FakeFileModel:
    def __init__(self, active_file_count: int) -> None:
        self.query = FakeFileQuery(active_file_count)

    def filter(self, **filters: Any) -> FakeFileQuery:
        return self.query.filter(**filters)


@pytest.mark.asyncio
async def test_folder_repository_counts_active_files(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(folder_module, "FolderModel", FakeFolderModel)
    monkeypatch.setattr(folder_module, "FileModel", FakeFileModel(3))

    folder = await FolderRepositoryImpl().get_by_id("folder-1")

    assert folder is not None
    assert folder.file_count == 3
