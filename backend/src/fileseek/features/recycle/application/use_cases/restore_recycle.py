from __future__ import annotations

from pathlib import Path
from typing import Any
from zipfile import ZipFile

from fileseek.config.constant import QUERY_CACHE_KEY
from fileseek.features.library.domain.repositories import FileRepository, FolderRepository
from fileseek.features.recycle.application.commands import RestoreItemsCommand
from fileseek.features.recycle.domain.exceptions import (
    RecycleItemNotFoundError,
)
from fileseek.features.recycle.domain.repositories import RecycleRepository
from fileseek.shared.utils.cache import TTLLRUCache


class RestoreRecycleUseCase:
    def __init__(
        self,
        recycle_repo: RecycleRepository,
        file_repo: FileRepository,
        folder_repo: FolderRepository,
        search_cache: TTLLRUCache[str, Any],
    ) -> None:
        self.recycle_repo = recycle_repo
        self.file_repo = file_repo
        self.folder_repo = folder_repo
        self.search_cache = search_cache

    async def execute(self, command: RestoreItemsCommand) -> None:
        try:
            for item_id in command.item_ids:
                await self._restore_item(item_id)
        finally:
            await self.search_cache.clear(QUERY_CACHE_KEY)

    async def _restore_item(self, item_id: str) -> None:
        item = await self.recycle_repo.get_by_id(item_id)

        if item is None:
            raise RecycleItemNotFoundError(f"回收站条目 {item_id} 不存在")

        # 1. 检查原父文件夹
        folder = None

        if item.original_folder_id:
            folder = await self.folder_repo.get_by_id(item.original_folder_id)

        if item.recycle_path is None:
            raise ValueError(f"回收站条目缺少压缩包路径: {item.id}")
        recycle_path = Path(item.recycle_path)
        restore_path = Path(item.original_path)
        with ZipFile(recycle_path) as archive:
            members = archive.namelist()
            if len(members) != 1:
                raise ValueError(f"回收站压缩包格式无效: {item.id}")
            restore_path.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(members[0]) as source, restore_path.open("wb") as target:
                while chunk := source.read(1024 * 1024):
                    target.write(chunk)
        recycle_path.unlink(missing_ok=True)

        # 6. 更新 Folder
        if folder:
            folder.increase_file_count()
            await self.folder_repo.save(folder)

        # 7. 删除回收站记录
        await self.recycle_repo.delete(item.id)
