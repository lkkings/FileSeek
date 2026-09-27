from __future__ import annotations

from fileseek.features.recycle.application.commands import RestoreItemsCommand
from fileseek.features.recycle.domain.exceptions import (
    RecycleItemNotFoundError,
)
from fileseek.features.library.domain.repositories import FileRepository, FolderRepository
from fileseek.features.recycle.domain.repositories import RecycleRepository
from fileseek.infrastructure.fs import VirtualPath


class RestoreRecycleUseCase:
    def __init__(
        self,
        recycle_repo: RecycleRepository,
        file_repo: FileRepository,
        folder_repo: FolderRepository
    ) -> None:
        self.recycle_repo = recycle_repo
        self.file_repo = file_repo
        self.folder_repo = folder_repo

    async def execute(self, command: RestoreItemsCommand) -> None:
        for item_id in command.item_ids:
            await self._restore_item(item_id)

    async def _restore_item(self, item_id: str) -> None:
        item = await self.recycle_repo.get_by_id(item_id)

        if item is None:
            raise RecycleItemNotFoundError(f"回收站条目 {item_id} 不存在")

        # 1. 检查原父文件夹
        folder = None

        if item.original_folder_id:
            folder = await self.folder_repo.get_by_id(item.original_folder_id)

        recycle_path = VirtualPath(item.recycle_path)
        restore_path = VirtualPath(item.original_path)
        recycle_path.decompress(restore_path)

        # 6. 更新 Folder
        if folder:
            folder.increase_file_count()
            await self.folder_repo.save(folder)

        # 7. 删除回收站记录
        await self.recycle_repo.delete(item.id)
