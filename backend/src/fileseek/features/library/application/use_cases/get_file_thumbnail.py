from __future__ import annotations

from typing import cast

from fileseek.features.library.application.dto import FileThumbnailDTO
from fileseek.features.library.application.ports import FileSourcePort, SourceFile
from fileseek.features.library.application.queries import GetFileThumbnailQuery
from fileseek.features.library.domain.entities import File
from fileseek.features.library.domain.exceptions import (
    FileNotFoundError,
    SourceUnavailableError,
    ThumbnailUnavailableError,
)
from fileseek.features.library.domain.repositories import FileRepository
from fileseek.infrastructure.thumbnail_cache import ThumbnailCache
from fileseek.infrastructure.thumbnails import (
    PreviewSize,
    ThumbnailGenerationError,
    ThumbnailGenerator,
)
from fileseek.shared.domain.exceptions import ValidationError
from fileseek.shared.domain.file_types import FileCategory


class GetFileThumbnailUseCase:
    """Returns a cached or freshly generated media thumbnail."""

    def __init__(
        self,
        file_repo: FileRepository,
        generator: ThumbnailGenerator,
        cache: ThumbnailCache,
        source_resolver: FileSourcePort,
    ) -> None:
        self._file_repo = file_repo
        self._generator = generator
        self._cache = cache
        self._source_resolver = source_resolver

    async def execute(self, query: GetFileThumbnailQuery) -> FileThumbnailDTO:
        if query.size not in ("list", "detail"):
            raise ValidationError("缩略图尺寸必须是 list 或 detail")

        file = await self._file_repo.get_by_id(query.file_id)
        if file is None:
            raise FileNotFoundError(f"文件不存在: {query.file_id}")

        if file.category not in (FileCategory.IMAGE, FileCategory.VIDEO):
            raise ValidationError("仅支持图片和视频生成缩略图")

        source = await self._get_source(file)

        size = cast(PreviewSize, query.size)
        source_modified = file.modified.isoformat()
        cached = self._cache.get(
            file_id=file.id,
            source_size=file.size,
            source_modified=source_modified,
            size=size,
        )
        if cached is not None:
            return self._to_dto(file, size, cached)

        data = (
            self._generate_image_thumbnail(source, size)
            if file.category is FileCategory.IMAGE
            else self._generate_video_thumbnail(source, size)
        )
        self._cache.store(
            file_id=file.id,
            source_size=file.size,
            source_modified=source_modified,
            size=size,
            data=data,
        )
        return self._to_dto(file, size, data)

    async def _get_source(self, file: File) -> SourceFile:
        if file.access_state == "unavailable":
            raise SourceUnavailableError(f"文件来源不可获取: {file.id}")

        source_available = False
        try:
            source = await self._source_resolver.resolve(
                file.storage_id or "local",
                file.path,
            )
            source_available = source.exists() and source.is_file()
        except SourceUnavailableError:
            await self._file_repo.set_access_state(file.id, "unavailable")
            raise
        if not source_available:
            await self._file_repo.set_access_state(file.id, "unavailable")
            raise SourceUnavailableError(f"文件来源不可获取: {file.id}")

        if file.access_state != "available":
            await self._file_repo.set_access_state(file.id, "available")
        return source

    def _generate_image_thumbnail(self, source: SourceFile, size: PreviewSize) -> bytes:
        try:
            with source.open("rb") as source_file:
                source_bytes = source_file.read()
        except OSError as exc:
            raise ThumbnailUnavailableError("缩略图源文件不可访问") from exc

        try:
            return self._generator.generate_image_thumbnail(source_bytes, size)
        except ThumbnailGenerationError as exc:
            raise ThumbnailUnavailableError("图片缩略图生成失败") from exc

    def _generate_video_thumbnail(
        self,
        source: SourceFile,
        size: PreviewSize,
    ) -> bytes:
        try:
            return self._generator.generate_video_thumbnail(str(source), size)
        except ThumbnailGenerationError as exc:
            raise ThumbnailUnavailableError("视频缩略图生成失败") from exc

    def _to_dto(self, file: File, size: PreviewSize, data: bytes) -> FileThumbnailDTO:
        return FileThumbnailDTO(
            id=file.id,
            size=size,
            data=data,
            source_size=file.size,
            source_modified=file.modified.isoformat(),
        )
