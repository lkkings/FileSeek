from __future__ import annotations

import logging
from pathlib import Path

from fileseek.features.library.domain.repositories import FileRepository
from fileseek.features.recycle.application.commands import DeletePermanentlyCommand
from fileseek.features.recycle.domain.exceptions import (
    RecycleItemNotFoundError,
)
from fileseek.features.recycle.domain.repositories import RecycleRepository
from fileseek.infrastructure.vector_store import VectorIndexPort

logger = logging.getLogger(__name__)


class DeleteRecycleUseCase:
    def __init__(
        self,
        recycle_repo: RecycleRepository,
        file_repo: FileRepository,
        vector_index: VectorIndexPort,
    ) -> None:
        self.recycle_repo = recycle_repo
        self.file_repo = file_repo
        self.vector_index = vector_index

    async def execute(self, command: DeletePermanentlyCommand) -> None:
        file_ids_to_delete: list[str] = []

        for item_id in command.item_ids:
            item = await self.recycle_repo.get_by_id(item_id)

            if item is None:
                raise RecycleItemNotFoundError(f"回收站条目 {item_id} 不存在")

            if item.recycle_path is None:
                raise ValueError(f"回收站条目缺少压缩包路径: {item.id}")
            recycle_path = Path(item.recycle_path)
            recycle_path.unlink(missing_ok=True)

            # 向量按 file_id 落盘，所以这里用 original_file_id（条目自己的 id 不是索引键）。
            # 必须在 delete() 落库之前：条目删掉之后就再也查不到该删哪些向量了。
            await self._delete_vectors(item.original_file_id)

            await self.recycle_repo.delete(item.id)
            file_ids_to_delete.append(item.original_file_id)

        if file_ids_to_delete:
            await self.file_repo.delete_batch(file_ids_to_delete)

    async def _delete_vectors(self, file_id: str) -> None:
        try:
            file = await self.file_repo.get_by_id(file_id)
            if file is not None:
                chunk_ids = [chunk.id for chunk in file.chunks]
                self.vector_index.delete_batch(chunk_ids)
        except Exception:
            logger.exception("删除文件 %s 的向量失败，向量库中可能残留", file_id)
