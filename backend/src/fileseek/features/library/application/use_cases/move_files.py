from typing import Any

from fileseek.config.constant import QUERY_CACHE_KEY
from fileseek.features.library.application.commands import MoveFilesCommand
from fileseek.features.library.domain.exceptions import FileNotFoundError, FolderNotFoundError
from fileseek.features.library.domain.repositories import FileRepository, FolderRepository
from fileseek.shared.domain.exceptions import ValidationError
from fileseek.shared.utils.cache import TTLLRUCache


class MoveFilesUseCase:
    def __init__(
        self,
        file_repo: FileRepository,
        folder_repo: FolderRepository,
        search_cache: TTLLRUCache[str, Any],
    ) -> None:
        self.file_repo = file_repo
        self.folder_repo = folder_repo
        self.search_cache = search_cache

    async def execute(self, command: MoveFilesCommand) -> int:
        file_ids = list(dict.fromkeys(command.file_ids))
        if not file_ids:
            raise ValidationError("至少选择一个文件")

        target_folder = await self.folder_repo.get_by_id(command.target_folder_id)
        if target_folder is None:
            raise FolderNotFoundError(f"文件夹 {command.target_folder_id} 不存在")

        files = []
        for file_id in file_ids:
            file = await self.file_repo.get_by_id(file_id)
            if file is None:
                raise FileNotFoundError(f"文件 {file_id} 不存在")
            files.append(file)

        for file in files:
            file.move_to_folder(command.target_folder_id)

        try:
            await self.file_repo.save_batch(files)
        finally:
            await self.search_cache.clear(QUERY_CACHE_KEY)

        return len(files)
