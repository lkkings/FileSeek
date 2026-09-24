"""Tests for ListFoldersUseCase."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from fileseek.features.library.application.use_cases.list_folders import ListFoldersUseCase
from fileseek.features.library.application.queries import ListFoldersQuery
from fileseek.features.library.domain.entities import Folder
from fileseek.features.library.domain.repositories import FolderRepository


@pytest.mark.asyncio
async def test_list_folders_success() -> None:
    folder_repo = AsyncMock(spec=FolderRepository)
    f1 = Folder(
        id="f_1",
        name="Docs",
        icon_type="icon-1",
        description="",
        modified="2026-01-01T00:00:00Z",
        file_count=2,
    )
    f2 = Folder(
        id="f_2",
        name="Photos",
        icon_type="icon-2",
        description="",
        modified="2026-01-02T00:00:00Z",
        file_count=10,
    )
    folder_repo.list_all.return_value = [f1, f2]

    use_case = ListFoldersUseCase(folder_repo)
    result = await use_case.execute(ListFoldersQuery())

    assert [item.id for item in result] == [f1.id, f2.id]
    folder_repo.list_all.assert_awaited_once()
