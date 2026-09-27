from __future__ import annotations

import logging

from fileseek.features.recycle.application.commands import ClearRecycleBinCommand
from fileseek.features.library.domain.repositories import FileRepository
from fileseek.features.recycle.domain.repositories import RecycleRepository
from fileseek.infrastructure.vector_store import VectorIndexPort
from fileseek.infrastructure.fs import VirtualPath

logger = logging.getLogger(__name__)


class ClearRecycleBinUseCase:
    def __init__(
        self,
        recycle_repo: RecycleRepository,
        file_repo: FileRepository,
        vector_index: VectorIndexPort,
    ) -> None:
        self.recycle_repo = recycle_repo
        self.file_repo = file_repo
        self.vector_index = vector_index

    async def execute(self, command: ClearRecycleBinCommand) -> None:
        items = await self.recycle_repo.list_all_items()

        file_ids_to_delete = []
        for item in items:
            recycle_path = VirtualPath(item.recycle_path)
            if recycle_path.exists():
                recycle_path.delete()
            await self._delete_vectors(item.original_file_id)
            file_ids_to_delete.append(item.original_file_id)

        await self.recycle_repo.delete_all()
        if file_ids_to_delete:
            await self.file_repo.delete_batch(file_ids_to_delete)

    async def _delete_vectors(self, file_id: str) -> None:
        try:
            file = await self.file_repo.get_by_id(file_id)
            chunk_ids = [chunk.id for chunk in file.chunks]
            self.vector_index.delete_batch(chunk_ids)
        except Exception:
            logger.exception("删除文件 %s 的向量失败，向量库中可能残留", file_id)
