from __future__ import annotations

import logging

from fileseek.features.library.application.commands import ClearRecycleBinCommand
from fileseek.features.library.domain.repositories import (
    RecycleRepository,
)
from fileseek.features.tasks.domain.ports import VectorIndexPort
from fileseek.infrastructure.fs import VirtualPath

logger = logging.getLogger(__name__)


class ClearRecycleBinUseCase:
    def __init__(
        self,
        recycle_repo: RecycleRepository,
        vector_index: VectorIndexPort,
    ) -> None:
        self.recycle_repo = recycle_repo
        self.vector_index = vector_index

    async def execute(self, command: ClearRecycleBinCommand) -> None:
        items = await self.recycle_repo.list_all_items()

        for item in items:
            recycle_path = VirtualPath(item.recycle_path)
            if recycle_path.exists():
                recycle_path.delete()
            self._delete_vectors(item.original_file_id)

        await self.recycle_repo.delete_all()

    def _delete_vectors(self, file_id: str) -> None:
        """删掉该文件的全部向量。失败只记日志，不中断清空。

        向量库是派生索引：文件此刻已经从磁盘删掉了，再把异常抛出去只会让回收站永远
        清不干净，用户也没有别的补救入口。残留向量下次检索会指向不存在的文件，由
        `accessible=False` 兜住，所以宁可留下可见的日志也不要卡住清空。
        """
        try:
            self.vector_index.delete_file_vectors(file_id)
        except Exception:
            logger.exception("删除文件 %s 的向量失败，向量库中可能残留", file_id)
