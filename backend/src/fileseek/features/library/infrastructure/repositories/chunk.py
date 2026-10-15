"""Library 文件夹的 Tortoise 仓储实现。"""

from typing import Sequence

from fileseek.features.library.domain.entities import FileChunk
from fileseek.features.library.domain.repositories import FileChunkRepository
from fileseek.infrastructure.database.models import FileChunkModel


class FileChunkRepositoryImpl(FileChunkRepository):
    """文件分块仓储实现。"""

    async def save(
        self,
        chunk: FileChunk,
    ) -> None:
        await FileChunkModel.update_or_create(
            id=chunk.id,
            defaults={
                "file_id": chunk.file_id,
                "content": chunk.content,
                "chunk_index": chunk.chunk_index,
            },
        )

    async def save_batch(
        self,
        chunks: Sequence[FileChunk],
    ) -> None:
        if not chunks:
            return

        models = [
            FileChunkModel(
                id=chunk.id,
                file_id=chunk.file_id,
                metadata=chunk.metadata,
            )
            for chunk in chunks
        ]

        await FileChunkModel.bulk_create(models)

    async def get_chunks_by_range(
        self,
        file_id: str,
        page: int | None = None,
        chunk_start: int | None = None,
        chunk_end: int | None = None,
    ) -> list[FileChunk]:
        """按范围查询文件 chunks。"""
        query = FileChunkModel.filter(file_id=file_id)

        # 按 page_number 过滤
        if page is not None:
            query = query.filter(metadata__page_number=page)

        # 按 line_number (段落编号) 范围过滤
        if chunk_start is not None:
            query = query.filter(metadata__line_number__gte=chunk_start)
        if chunk_end is not None:
            query = query.filter(metadata__line_number__lte=chunk_end)

        # 按 chunk_index 排序
        models = await query.order_by("metadata__chunk_index").all()

        return [
            FileChunk(
                id=model.id,
                file_id=model.file_id,
                metadata=model.metadata,
            )
            for model in models
        ]
