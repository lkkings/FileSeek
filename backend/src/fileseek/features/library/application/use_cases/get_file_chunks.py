"""获取文件 chunks 的 use case。"""

from fileseek.features.library.domain.repositories import FileChunkRepository, FileRepository
from fileseek.shared.domain.exceptions import NotFoundError


class GetFileChunksQuery:
    """获取文件 chunks 查询。"""

    def __init__(
        self,
        file_id: str,
        page: int | None = None,
        chunk_start: int | None = None,
        chunk_end: int | None = None,
    ):
        self.file_id = file_id
        self.page = page
        self.chunk_start = chunk_start
        self.chunk_end = chunk_end


class FileChunkDTO:
    """文件 chunk DTO。"""

    def __init__(
        self,
        text: str,
        page_number: int | None,
        line_number: int | None,
        chunk_index: int,
    ):
        self.text = text
        self.page_number = page_number
        self.line_number = line_number
        self.chunk_index = chunk_index


class GetFileChunksResult:
    """获取文件 chunks 结果。"""

    def __init__(
        self,
        chunks: list[FileChunkDTO],
        total_chunks: int,
        page_count: int | None = None,
    ):
        self.chunks = chunks
        self.total_chunks = total_chunks
        self.page_count = page_count


class GetFileChunksUseCase:
    """获取文件 chunks。"""

    def __init__(
        self,
        file_repo: FileRepository,
        chunk_repo: FileChunkRepository,
    ):
        self.file_repo = file_repo
        self.chunk_repo = chunk_repo

    async def execute(self, query: GetFileChunksQuery) -> GetFileChunksResult:
        # 验证文件存在
        file = await self.file_repo.get_by_id(query.file_id)
        if file is None:
            raise NotFoundError(f"文件不存在: {query.file_id}")

        # 查询 chunks
        chunks = await self.chunk_repo.get_chunks_by_range(
            file_id=query.file_id,
            page=query.page,
            chunk_start=query.chunk_start,
            chunk_end=query.chunk_end,
        )

        # 转换为 DTO
        chunk_dtos = [
            FileChunkDTO(
                text=chunk.metadata.get("text", ""),
                page_number=chunk.metadata.get("page_number"),
                line_number=chunk.metadata.get("line_number"),
                chunk_index=chunk.metadata.get("chunk_index", 0),
            )
            for chunk in chunks
        ]

        # 计算总数和页数（简化实现，实际可能需要单独查询）
        # TODO: 如果需要精确的 total_chunks 和 page_count，需要额外查询
        total_chunks = len(chunk_dtos)
        page_count = None
        if chunks:
            max_page = max(
                (c.metadata.get("page_number") or 0 for c in chunks),
                default=None,
            )
            if max_page is not None:
                page_count = max_page

        return GetFileChunksResult(
            chunks=chunk_dtos,
            total_chunks=total_chunks,
            page_count=page_count,
        )
