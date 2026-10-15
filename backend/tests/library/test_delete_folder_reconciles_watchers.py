from __future__ import annotations

from datetime import UTC, datetime

import pytest

from fileseek.features.library.application.commands import DeleteFolderCommand
from fileseek.features.library.application.use_cases import DeleteFolderUseCase
from fileseek.features.library.domain.entities import Folder


class FakeFolderRepository:
    async def get_by_id(self, folder_id: str) -> Folder:
        return Folder(
            id=folder_id,
            name="Watched",
            icon_type="default",
            description="",
            modified=datetime.now(UTC),
        )

    async def delete(self, folder_id: str) -> None:
        _ = folder_id


class FakeWatcher:
    def __init__(self) -> None:
        self.reconciled = 0

    async def reconcile(self) -> None:
        self.reconciled += 1


@pytest.mark.asyncio
async def test_delete_folder_reconciles_source_watchers() -> None:
    watcher = FakeWatcher()
    use_case = DeleteFolderUseCase(FakeFolderRepository(), watcher)

    await use_case.execute(DeleteFolderCommand("folder-1"))

    assert watcher.reconciled == 1
