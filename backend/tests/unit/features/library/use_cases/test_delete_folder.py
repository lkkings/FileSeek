"""Tests for DeleteFolderUseCase."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from fileseek.features.library.application.use_cases.delete_folder import DeleteFolderUseCase
from fileseek.features.library.domain.entities import Folder
from fileseek.features.library.domain.exceptions import FolderNotEmptyError, FolderNotFoundError
from fileseek.features.library.domain.repositories import FolderRepository


@pytest.mark.asyncio
async def test_delete_folder_success() -> None:
    folder_repo = AsyncMock(spec=FolderRepository)
    empty_folder = Folder(
        id="f_100",
        name="Empty",
        icon_type="folder",
        description="",
        modified="2026-01-01T00:00:00Z",
        file_count=0,
    )
    folder_repo.get_by_id.return_value = empty_folder

    use_case = DeleteFolderUseCase(folder_repo)
    await use_case.execute("f_100")

    folder_repo.delete.assert_awaited_once_with("f_100")


@pytest.mark.asyncio
async def test_delete_folder_not_found() -> None:
    folder_repo = AsyncMock(spec=FolderRepository)
    folder_repo.get_by_id.return_value = None

    use_case = DeleteFolderUseCase(folder_repo)
    with pytest.raises(FolderNotFoundError, match="文件夹 f_999 不存在"):
        await use_case.execute("f_999")

    folder_repo.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_folder_not_empty() -> None:
    folder_repo = AsyncMock(spec=FolderRepository)
    non_empty_folder = Folder(
        id="f_200",
        name="Non Empty",
        icon_type="folder",
        description="",
        modified="2026-01-01T00:00:00Z",
        file_count=5,
    )
    folder_repo.get_by_id.return_value = non_empty_folder

    use_case = DeleteFolderUseCase(folder_repo)
    with pytest.raises(FolderNotEmptyError, match="文件夹非空"):
        await use_case.execute("f_200")

    folder_repo.delete.assert_not_awaited()
