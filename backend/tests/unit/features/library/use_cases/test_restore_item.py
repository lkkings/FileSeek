"""Tests for RestoreRecycleUseCase."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from fileseek.features.library.application.use_cases.restore_recycle import RestoreRecycleUseCase
from fileseek.features.library.application.commands import RestoreItemCommand
from fileseek.features.library.domain.entities import Folder, RecycleItem
from fileseek.features.library.domain.exceptions import RecycleItemNotFoundError
from fileseek.features.library.domain.repositories import (
    FileRepository,
    FolderRepository,
    RecycleRepository,
)
from fileseek.shared.domain.file_types import FileType
from fileseek.shared.domain.ports import FileSystemPort, FileSystemResolver


@pytest.mark.asyncio
async def test_restore_item_success_with_folder() -> None:
    recycle_repo = AsyncMock(spec=RecycleRepository)
    file_repo = AsyncMock(spec=FileRepository)
    folder_repo = AsyncMock(spec=FolderRepository)
    resolver = MagicMock(spec=FileSystemResolver)
    file = MagicMock(spec=FileSystemPort)
    resolver.resolve.return_value = file

    item = RecycleItem(
        id="r_100",
        original_file_id="file_100",
        original_name="restored.docx",
        original_path="/docs/restored.docx",
        deleted_at="2026-01-01T00:00:00Z",
        file_type=FileType.DOCUMENT,
        size=1024,
        original_parent_folder="f_50",
        recycle_path="/trash/restored.docx",
    )
    recycle_repo.get_by_id.return_value = item

    folder = Folder(
        id="f_50",
        name="Docs",
        icon_type="folder",
        description="",
        modified="2026-01-01T00:00:00Z",
        file_count=0,
    )
    folder_repo.get_by_id.return_value = folder

    use_case = RestoreRecycleUseCase(
        recycle_repo,
        file_repo,
        folder_repo,
        resolver,
    )
    await use_case.execute(RestoreItemCommand("r_100"))

    # Physical file restoration: resolve the recycle location, restore to the original path
    resolver.resolve.assert_called_once_with("/trash/restored.docx")
    # 还原是对回收站里那个压缩包 decompress，不是把原文件 move 回去：删除时
    # `AddFiles2RecycleUseCase` 把文件压成了包，`original_path` 记的是包的路径。
    file.decompress.assert_called_once()

    # Saved File entity
    file_repo.save.assert_awaited_once()
    saved_file = file_repo.save.call_args[0][0]
    assert saved_file.id == "file_100"
    assert saved_file.name == "restored.docx"
    assert saved_file.parent_folder == "f_50"

    # Updated Folder
    assert folder.file_count == 1
    folder_repo.save.assert_awaited_once_with(folder)

    # Deleted recycle item
    recycle_repo.delete.assert_awaited_once_with("r_100")


@pytest.mark.asyncio
async def test_restoring_into_a_deleted_folder_lands_in_the_root() -> None:
    """原文件夹已被删除时还原到根目录，而不是写回一个不存在的 id。

    `FileModel.parent_folder` 是指向 folders 表的外键，写回一个已删除的文件夹 id 会撞
    FOREIGN KEY 约束，整个还原变成 500——而用户能做出这个动作：删文件 → 删空文件夹 →
    去回收站点还原。
    """
    recycle_repo = AsyncMock(spec=RecycleRepository)
    file_repo = AsyncMock(spec=FileRepository)
    folder_repo = AsyncMock(spec=FolderRepository)
    resolver = MagicMock(spec=FileSystemResolver)
    resolver.resolve.return_value = MagicMock(spec=FileSystemPort)

    recycle_repo.get_by_id.return_value = RecycleItem(
        id="r_200",
        original_file_id="file_200",
        original_name="orphan.pdf",
        original_path="/docs/orphan.pdf",
        deleted_at="2026-01-01T00:00:00Z",
        file_type=FileType.DOCUMENT,
        size=2048,
        original_parent_folder="d_gone",
        recycle_path="/trash/orphan.zip",
    )
    # 文件夹已经不在了。
    folder_repo.get_by_id.return_value = None

    use_case = RestoreRecycleUseCase(recycle_repo, file_repo, folder_repo, resolver)
    await use_case.execute(RestoreItemCommand("r_200"))

    saved_file = file_repo.save.await_args.args[0]
    assert saved_file.parent_folder is None
    # 没有文件夹可以加计数。
    folder_repo.save.assert_not_awaited()
    recycle_repo.delete.assert_awaited_once_with("r_200")


@pytest.mark.asyncio
async def test_restore_item_not_found() -> None:
    recycle_repo = AsyncMock(spec=RecycleRepository)
    file_repo = AsyncMock(spec=FileRepository)
    folder_repo = AsyncMock(spec=FolderRepository)
    resolver = MagicMock(spec=FileSystemResolver)

    recycle_repo.get_by_id.return_value = None

    use_case = RestoreRecycleUseCase(
        recycle_repo,
        file_repo,
        folder_repo,
        resolver,
    )
    with pytest.raises(RecycleItemNotFoundError, match="回收站条目 r_missing 不存在"):
        await use_case.execute(RestoreItemCommand("r_missing"))

    resolver.resolve.assert_not_called()
    file_repo.save.assert_not_awaited()
