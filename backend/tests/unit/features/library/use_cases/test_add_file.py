"""Tests for AddFileUseCase.

这里主要盯着文件夹计数。计数是两侧配对的：入库 +1（本用例），移入回收站 -1
（`AddFiles2RecycleUseCase`）。少了任何一侧，计数就会单向漂移——而
`Folder.ensure_can_delete` 拿它判断文件夹能不能删，漂了就会放过一个还有文件的文件夹。
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from fileseek.features.library.application.commands import AddFileCommand
from fileseek.features.library.application.use_cases.add_file import AddFileUseCase
from fileseek.features.library.domain.entities import Folder
from fileseek.features.library.domain.repositories import (
    FileRepository,
    FolderRepository,
)
from fileseek.features.tasks.domain.ports import TaskManager
from fileseek.shared.domain.ports import FileSystemPort, FileSystemResolver


@pytest.fixture
def source(tmp_path: Path) -> Path:
    """一个真实存在的待入库文件。用例会 stat 落盘后的文件，所以不能是纯 mock。"""
    path = tmp_path / "报告.txt"
    path.write_text("内容", encoding="utf-8")
    return path


def _use_case(tmp_path: Path, source: Path, folder: Folder | None):
    """装好各路替身的用例，外加它依赖的两个仓库以便断言。"""
    file_repo = AsyncMock(spec=FileRepository)
    folder_repo = AsyncMock(spec=FolderRepository)
    folder_repo.get_by_id.return_value = folder
    task_manager = AsyncMock(spec=TaskManager)

    # `move_to` 真的把文件挪过去：之后用例要 stat 目标路径拿体积和 mtime。
    handle = MagicMock(spec=FileSystemPort)
    handle.exists.return_value = True
    handle.is_accessible.return_value = True
    handle.read_bytes.return_value = source.read_bytes()

    def move_to(dest: str | Path) -> Path:
        target = Path(dest)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
        return target

    handle.move_to.side_effect = move_to

    resolver = MagicMock(spec=FileSystemResolver)
    resolver.resolve.return_value = handle

    use_case = AddFileUseCase(file_repo, folder_repo, resolver, task_manager)
    return use_case, file_repo, folder_repo, task_manager


@pytest.mark.asyncio
async def test_adding_a_file_to_a_folder_raises_its_count(tmp_path: Path, source: Path) -> None:
    folder = Folder(
        id="d_1",
        name="工作",
        icon_type="work",
        description="",
        modified="2026-01-01T00:00:00Z",
        file_count=0,
    )
    use_case, _, folder_repo, _ = _use_case(tmp_path, source, folder)

    await use_case.execute(AddFileCommand("d_1", "报告.txt", str(source)))

    # 没有这一笔，导入完计数还是 0，删一次就掉到 -1。
    folder_repo.increment_file_count.assert_awaited_once_with("d_1", 1)


@pytest.mark.asyncio
async def test_adding_a_file_to_the_root_touches_no_folder(tmp_path: Path, source: Path) -> None:
    use_case, _, folder_repo, _ = _use_case(tmp_path, source, None)

    await use_case.execute(AddFileCommand(None, "报告.txt", str(source)))

    # 根目录没有文件夹可计数。
    folder_repo.increment_file_count.assert_not_awaited()


@pytest.mark.asyncio
async def test_adding_a_file_queues_its_indexing_task(tmp_path: Path, source: Path) -> None:
    use_case, _, _, task_manager = _use_case(tmp_path, source, None)

    file_id = await use_case.execute(AddFileCommand(None, "报告.txt", str(source)))

    # 入库即建向量化任务，所以前端不需要再单独调 /tasks。
    task_manager.create.assert_awaited_once()
    assert task_manager.create.await_args.args[0] == file_id


@pytest.mark.asyncio
async def test_saved_file_records_where_it_landed(tmp_path: Path, source: Path) -> None:
    use_case, file_repo, _, _ = _use_case(tmp_path, source, None)

    await use_case.execute(AddFileCommand(None, "报告.txt", str(source)))

    saved = file_repo.save.await_args.args[0]
    # 存的是落盘后的库内路径，不是调用方传进来的源路径——源文件已经被移走了。
    assert saved.path != str(source)
    assert Path(saved.path).exists()
    assert saved.size == source.stat().st_size
