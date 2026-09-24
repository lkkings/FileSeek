"""Tests for UpdateFolderUseCase."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from fileseek.features.library.application.use_cases.update_folder import UpdateFolderUseCase
from fileseek.features.library.application.commands import UpdateFolderCommand
from fileseek.features.library.domain.entities import Folder
from fileseek.features.library.domain.exceptions import FolderNotFoundError
from fileseek.features.library.domain.repositories import FolderRepository


@pytest.mark.asyncio
async def test_update_folder_success() -> None:
    folder_repo = AsyncMock(spec=FolderRepository)
    existing_folder = Folder(
        id="f_123",
        name="Old Name",
        icon_type="icon-old",
        description="Old desc",
        modified="2026-01-01T00:00:00Z",
        file_count=2,
    )
    folder_repo.get_by_id.return_value = existing_folder

    use_case = UpdateFolderUseCase(folder_repo)
    updated_folder = await use_case.execute(
        UpdateFolderCommand("f_123", "New Name", "icon-new", "New desc")
    )

    assert updated_folder.name == "New Name"
    assert updated_folder.icon_type == "icon-new"
    assert updated_folder.description == "New desc"
    assert updated_folder.file_count == 2
    folder_repo.save.assert_awaited_once_with(existing_folder)


@pytest.mark.asyncio
async def test_update_folder_not_found() -> None:
    folder_repo = AsyncMock(spec=FolderRepository)
    folder_repo.get_by_id.return_value = None

    use_case = UpdateFolderUseCase(folder_repo)
    with pytest.raises(FolderNotFoundError, match="文件夹 f_999 不存在"):
        await use_case.execute(UpdateFolderCommand("f_999", "New Name", "icon", "desc"))


@pytest.mark.asyncio
async def test_update_folder_empty_name() -> None:
    folder_repo = AsyncMock(spec=FolderRepository)
    existing_folder = Folder(
        id="f_123",
        name="Old Name",
        icon_type="icon-old",
        description="Old desc",
        modified="2026-01-01T00:00:00Z",
        file_count=0,
    )
    folder_repo.get_by_id.return_value = existing_folder

    use_case = UpdateFolderUseCase(folder_repo)
    with pytest.raises(ValueError, match="文件夹名称不能为空"):
        await use_case.execute(UpdateFolderCommand("f_123", "   ", "icon-new", "desc"))
