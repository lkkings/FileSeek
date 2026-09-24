from __future__ import annotations

import logging

from fileseek.features.library.application.commands import DeletePermanentlyCommand
from fileseek.features.library.domain.exceptions import (
    RecycleItemNotFoundError,
)
from fileseek.features.library.domain.repositories import (
    RecycleRepository,
)
from fileseek.features.tasks.domain.ports import VectorIndexPort
from fileseek.infrastructure.fs import VirtualPath

logger = logging.getLogger(__name__)


class DeleteRecycleUseCase:
    def __init__(
        self,
        recycle_repo: RecycleRepository,
        vector_index: VectorIndexPort,
    ) -> None:
        self.recycle_repo = recycle_repo
        self.vector_index = vector_index

    async def execute(self, command: DeletePermanentlyCommand) -> None:
        item_id = command.item_id
        item = await self.recycle_repo.get_by_id(item_id)

        if item is None:
            raise RecycleItemNotFoundError(f"回收站条目 {item_id} 不存在")

        recycle_path = VirtualPath(item.recycle_path)
        if recycle_path.exists():
            recycle_path.delete()

        # 向量按 file_id 落盘，所以这里用 original_file_id（条目自己的 id 不是索引键）。
        # 必须在 delete() 落库之前：条目删掉之后就再也查不到该删哪些向量了。
        self._delete_vectors(item.original_file_id)

        await self.recycle_repo.delete(item.id)

    def _delete_vectors(self, file_id: str) -> None:
        """删掉该文件的全部向量。失败只记日志，不中断删除。

        向量库是派生索引：文件此刻已经从磁盘删掉了，再把异常抛出去会让条目留在回收站里
        指向一个不存在的文件，而用户没有别的补救入口。残留向量下次检索指向不存在的文件，
        由 `accessible=False` 兜住。
        """
        try:
            self.vector_index.delete_file_vectors(file_id)
        except Exception:
            logger.exception("删除文件 %s 的向量失败，向量库中可能残留", file_id)
