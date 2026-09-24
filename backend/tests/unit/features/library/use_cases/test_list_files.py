"""Tests for ListFilesUseCase."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from fileseek.features.library.application.use_cases.list_files import ListFilesUseCase
from fileseek.features.library.application.queries import ListFilesQuery
from fileseek.features.library.domain.entities import File, Folder
from fileseek.features.library.domain.repositories import FileRepository, FolderRepository
from fileseek.shared.domain.file_types import FileType


@pytest.mark.asyncio
async def test_list_files_no_folder_filter() -> None:
    file_repo = AsyncMock(spec=FileRepository)
    folder_repo = AsyncMock(spec=FolderRepository)

    sample_file = File(
        id="file_1",
        name="test.txt",
        file_type=FileType.DOCUMENT,
        size=100,
        modified="2026-01-01T00:00:00Z",
        path="/path/test.txt",
    )
    file_repo.list_by_folder.return_value = ([sample_file], 1)

    use_case = ListFilesUseCase(file_repo, folder_repo)
    files, total = await use_case.execute(ListFilesQuery(None, "text", 1, 20))

    assert files[0].id == sample_file.id
    assert total == 1
    file_repo.list_by_folder.assert_awaited_once_with(
        folder_id=None,
        file_type="text",
        page=1,
        page_size=20,
    )


@pytest.mark.asyncio
async def test_list_files_with_existing_folder_name() -> None:
    file_repo = AsyncMock(spec=FileRepository)
    folder_repo = AsyncMock(spec=FolderRepository)

    folder = Folder(
        id="f_100",
        name="Work",
        icon_type="folder",
        description="",
        modified="2026-01-01T00:00:00Z",
        file_count=1,
    )
    folder_repo.get_by_name.return_value = folder

    sample_file = File(
        id="file_1",
        name="report.pdf",
        file_type=FileType.DOCUMENT,
        size=2048,
        modified="2026-01-01T00:00:00Z",
        path="/work/report.pdf",
        parent_folder="f_100",
    )
    file_repo.list_by_folder.return_value = ([sample_file], 1)

    use_case = ListFilesUseCase(file_repo, folder_repo)
    files, total = await use_case.execute(ListFilesQuery("Work", None, 1, 10))

    assert files[0].id == sample_file.id
    assert total == 1
    folder_repo.get_by_name.assert_awaited_once_with("Work")
    file_repo.list_by_folder.assert_awaited_once_with(
        folder_id="f_100",
        file_type=None,
        page=1,
        page_size=10,
    )


@pytest.mark.asyncio
async def test_list_files_with_nonexistent_folder_name() -> None:
    file_repo = AsyncMock(spec=FileRepository)
    folder_repo = AsyncMock(spec=FolderRepository)
    folder_repo.get_by_name.return_value = None

    use_case = ListFilesUseCase(file_repo, folder_repo)
    files, total = await use_case.execute(ListFilesQuery("UnknownFolder", None, 1, 10))

    assert files == []
    assert total == 0
    file_repo.list_by_folder.assert_not_awaited()
