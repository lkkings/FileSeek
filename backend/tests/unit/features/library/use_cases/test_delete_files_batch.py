"""Tests for AddFiles2RecycleUseCase."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from fileseek.features.library.application.use_cases.add_files2recycle import (
    AddFiles2RecycleUseCase,
)
from fileseek.features.library.application.commands import AddFiles2RecycleCommand
from fileseek.features.library.domain.entities import File
from fileseek.shared.domain.ports import FileSystemPort, FileSystemResolver
from fileseek.features.library.domain.repositories import (
    FileRepository,
    FolderRepository,
    RecycleRepository,
)
from fileseek.shared.domain.file_types import FileType


@pytest.mark.asyncio
async def test_delete_files_batch_success() -> None:
    file_repo = AsyncMock(spec=FileRepository)
    folder_repo = AsyncMock(spec=FolderRepository)
    recycle_repo = AsyncMock(spec=RecycleRepository)

    file_1 = File(
        id="file_1",
        name="a.png",
        file_type=FileType.IMAGE,
        size=500,
        modified="2026-01-01T00:00:00Z",
        path="/a.png",
        parent_folder="f_1",
    )
    file_2 = File(
        id="file_2",
        name="b.pdf",
        file_type=FileType.DOCUMENT,
        size=1500,
        modified="2026-01-01T00:00:00Z",
        path="/b.pdf",
        parent_folder=None,
    )

    file_repo.get_by_id.side_effect = lambda fid: {
        "file_1": file_1,
        "file_2": file_2,
    }.get(fid)

    resolver = MagicMock(spec=FileSystemResolver)
    resolver.resolve.return_value = MagicMock(spec=FileSystemPort)
    use_case = AddFiles2RecycleUseCase(file_repo, folder_repo, recycle_repo, resolver)
    await use_case.execute(AddFiles2RecycleCommand(["file_1", "file_2", "non_existent_file"]))

    # Saves 2 items to recycle bin
    assert recycle_repo.save.call_count == 2

    # Deletes file_1 and file_2 from file_repo
    file_repo.delete.assert_any_call("file_1")
    file_repo.delete.assert_any_call("file_2")
    assert file_repo.delete.call_count == 2

    # Decrements file count for parent folder of file_1 only
    folder_repo.increment_file_count.assert_awaited_once_with("f_1", -1)
