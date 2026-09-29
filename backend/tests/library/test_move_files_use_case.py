from typing import Any
from unittest.mock import AsyncMock

import pytest

from fileseek.config.constant import QUERY_CACHE_KEY
from fileseek.features.library.application.commands import MoveFilesCommand
from fileseek.features.library.application.use_cases import MoveFilesUseCase
from fileseek.features.library.domain.entities import File
from fileseek.features.library.domain.exceptions import FileNotFoundError, FolderNotFoundError
from fileseek.shared.domain.exceptions import ValidationError
from fileseek.shared.domain.file_types import FileCategory, FileType
from fileseek.shared.utils.cache import TTLLRUCache


def create_file(file_id: str, folder_id: str) -> File:
    return File(
        id=file_id,
        name=f"{file_id}.png",
        file_type=FileType.PNG,
        category=FileCategory.IMAGE,
        size=100,
        modified="2026-09-28T00:00:00Z",
        path=f"/files/{file_id}.png",
        folder_id=folder_id,
    )


def create_use_case(
    file_repo: Any,
    folder_repo: Any,
) -> tuple[MoveFilesUseCase, TTLLRUCache[str, Any]]:
    cache = TTLLRUCache()
    return MoveFilesUseCase(file_repo, folder_repo, cache), cache


@pytest.mark.asyncio
async def test_moves_all_files_and_updates_counts():
    files = [create_file("file-1", "folder-1"), create_file("file-2", "folder-1")]
    file_repo = AsyncMock()
    file_repo.get_by_id.side_effect = files
    folder_repo = AsyncMock()
    folder_repo.get_by_id.return_value = object()
    use_case, cache = create_use_case(file_repo, folder_repo)
    await cache.set(QUERY_CACHE_KEY, "query", {"items": ["file-1"]})

    moved_count = await use_case.execute(
        MoveFilesCommand(("file-1", "file-2", "file-1"), "folder-2"),
    )

    assert moved_count == 2
    assert [file.folder_id for file in files] == ["folder-2", "folder-2"]
    file_repo.save_batch.assert_awaited_once_with(files)
    assert await cache.get(QUERY_CACHE_KEY, "query") is None


@pytest.mark.asyncio
async def test_rejects_empty_file_ids():
    file_repo = AsyncMock()
    folder_repo = AsyncMock()
    use_case, _ = create_use_case(file_repo, folder_repo)

    with pytest.raises(ValidationError):
        await use_case.execute(MoveFilesCommand((), "folder-2"))


@pytest.mark.asyncio
async def test_fails_before_mutation_when_target_is_missing():
    file_repo = AsyncMock()
    folder_repo = AsyncMock()
    folder_repo.get_by_id.return_value = None
    use_case, _ = create_use_case(file_repo, folder_repo)

    with pytest.raises(FolderNotFoundError):
        await use_case.execute(MoveFilesCommand(("file-1",), "missing-folder"))

    file_repo.save_batch.assert_not_awaited()


@pytest.mark.asyncio
async def test_fails_before_mutation_when_file_is_missing():
    file_repo = AsyncMock()
    file_repo.get_by_id.return_value = None
    folder_repo = AsyncMock()
    folder_repo.get_by_id.return_value = object()
    use_case, _ = create_use_case(file_repo, folder_repo)

    with pytest.raises(FileNotFoundError):
        await use_case.execute(MoveFilesCommand(("missing-file",), "folder-2"))

    file_repo.save_batch.assert_not_awaited()
