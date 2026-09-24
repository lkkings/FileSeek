"""Tests for CreateFolderUseCase."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from fileseek.features.library.application.use_cases.create_folder import CreateFolderUseCase
from fileseek.features.library.application.commands import CreateFolderCommand
from fileseek.features.library.domain.repositories import FolderRepository


@pytest.mark.asyncio
async def test_create_folder_success() -> None:
    folder_repo = AsyncMock(spec=FolderRepository)
    use_case = CreateFolderUseCase(folder_repo)

    folder = await use_case.execute(
        CreateFolderCommand("Documents", "folder-blue", "My document collection")
    )

    assert folder.name == "Documents"
    assert folder.name == "Documents"
    assert folder.icon_type == "folder-blue"
    assert folder.description == "My document collection"
    assert folder.file_count == 0
    assert folder.id.startswith("d_")

    folder_repo.save.assert_awaited_once()
