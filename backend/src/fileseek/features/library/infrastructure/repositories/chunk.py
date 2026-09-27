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

        await FileChunkModel.bulk_create(
            models
        )