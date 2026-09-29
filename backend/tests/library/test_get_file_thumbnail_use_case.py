from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image
from pypdf import PdfWriter

from fileseek.features.library.application.queries import GetFileThumbnailQuery
from fileseek.features.library.application.use_cases.get_file_thumbnail import (
    GetFileThumbnailUseCase,
)
from fileseek.features.library.domain.entities import File
from fileseek.features.library.domain.exceptions import (
    FileNotFoundError,
    SourceUnavailableError,
)
from fileseek.features.settings.infrastructure.source_access import LocalSourceFile
from fileseek.infrastructure.thumbnail_cache import ThumbnailCache
from fileseek.infrastructure.thumbnails import ThumbnailGenerator
from fileseek.shared.domain.exceptions import ValidationError
from fileseek.shared.domain.file_types import FileCategory, FileType


class FakeFileRepository:
    def __init__(self, file: File | None) -> None:
        self._file = file

    async def get_by_id(self, file_id: str) -> File | None:
        if self._file is None:
            return None
        return self._file if file_id == self._file.id else None

    async def set_access_state(self, file_id: str, access_state: str) -> bool:
        _ = file_id
        assert self._file is not None
        self._file.access_state = access_state
        return True


class FakeSourceResolver:
    def __init__(self, resolve_error: bool = False) -> None:
        self.resolve_error = resolve_error

    async def resolve(self, storage_id: str, source_path: str):
        _ = storage_id
        if self.resolve_error:
            raise SourceUnavailableError("文件来源不可获取: file-1")
        return LocalSourceFile(Path(source_path))


def create_image(path: Path, width: int = 320, height: int = 180) -> None:
    image = Image.new("RGB", (width, height), "#3366aa")
    image.save(path, format="PNG")


def create_pdf(path: Path, width: int = 200, height: int = 100) -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=width, height=height)
    with path.open("wb") as pdf_file:
        writer.write(pdf_file)


def create_file(
    path: Path,
    category: FileCategory = FileCategory.IMAGE,
    size: int | None = None,
) -> File:
    return File(
        id="file-1",
        name="source.png",
        file_type=FileType.PNG,
        category=category,
        size=size if size is not None else path.stat().st_size,
        modified=datetime(2026, 9, 28, 8, tzinfo=UTC),
        path=str(path),
    )


@pytest.mark.asyncio
async def test_generates_and_caches_an_image_thumbnail(tmp_path: Path):
    source = tmp_path / "source.png"
    create_image(source)
    file = create_file(source, size=100)
    repository = FakeFileRepository(file)
    cache = ThumbnailCache(tmp_path / "cache")
    use_case = GetFileThumbnailUseCase(
        repository,
        ThumbnailGenerator(),
        cache,
        FakeSourceResolver(),
    )
    query = GetFileThumbnailQuery(file_id="file-1", size="list")

    thumbnail = await use_case.execute(query)
    cached_thumbnail = await use_case.execute(query)

    assert thumbnail.id == "file-1"
    assert thumbnail.size == "list"
    with Image.open(BytesIO(thumbnail.data)) as image:
        assert image.format == "WEBP"
        assert image.size == (96, 54)
    assert cached_thumbnail.data == thumbnail.data


@pytest.mark.asyncio
async def test_generates_a_pdf_thumbnail(tmp_path: Path):
    source = tmp_path / "document.pdf"
    create_pdf(source)
    file = create_file(source, FileCategory.DOCUMENT)
    file.file_type = FileType.PDF
    use_case = GetFileThumbnailUseCase(
        FakeFileRepository(file),
        ThumbnailGenerator(),
        ThumbnailCache(tmp_path / "cache"),
        FakeSourceResolver(),
    )
    query = GetFileThumbnailQuery(file_id="file-1", size="list")

    thumbnail = await use_case.execute(query)

    with Image.open(BytesIO(thumbnail.data)) as image:
        assert image.format == "WEBP"
        assert image.size == (96, 48)


@pytest.mark.asyncio
async def test_rejects_non_pdf_documents_for_thumbnail_generation(tmp_path: Path):
    source = tmp_path / "document.docx"
    source.write_bytes(b"not a docx")
    file = create_file(source, FileCategory.DOCUMENT)
    file.file_type = FileType.DOCX
    use_case = GetFileThumbnailUseCase(
        FakeFileRepository(file),
        ThumbnailGenerator(),
        ThumbnailCache(tmp_path / "cache"),
        FakeSourceResolver(),
    )

    with pytest.raises(ValidationError, match="图片、视频和 PDF"):
        await use_case.execute(GetFileThumbnailQuery(file_id="file-1", size="list"))


@pytest.mark.asyncio
async def test_rejects_removed_image_types_for_thumbnail_generation(
    tmp_path: Path,
) -> None:
    source = tmp_path / "graphic.svg"
    source.write_text("<svg xmlns='http://www.w3.org/2000/svg'></svg>")
    file = create_file(source)
    file.file_type = FileType.SVG
    use_case = GetFileThumbnailUseCase(
        FakeFileRepository(file),
        ThumbnailGenerator(),
        ThumbnailCache(tmp_path / "cache"),
        FakeSourceResolver(),
    )

    with pytest.raises(ValidationError, match="图片、视频和 PDF"):
        await use_case.execute(GetFileThumbnailQuery(file_id="file-1", size="list"))


@pytest.mark.asyncio
async def test_reports_inaccessible_source_without_path_details(tmp_path: Path):
    source = tmp_path / "missing.png"
    file = create_file(source, size=100)
    use_case = GetFileThumbnailUseCase(
        FakeFileRepository(file),
        ThumbnailGenerator(),
        ThumbnailCache(tmp_path / "cache"),
        FakeSourceResolver(),
    )

    with pytest.raises(SourceUnavailableError, match="不可获取"):
        await use_case.execute(GetFileThumbnailQuery(file_id="file-1", size="list"))
    assert file.access_state == "unavailable"


@pytest.mark.asyncio
async def test_thumbnail_keeps_state_when_resolver_fails(tmp_path: Path):
    source = tmp_path / "missing.png"
    file = create_file(source, size=100)
    use_case = GetFileThumbnailUseCase(
        FakeFileRepository(file),
        ThumbnailGenerator(),
        ThumbnailCache(tmp_path / "cache"),
        FakeSourceResolver(resolve_error=True),
    )

    with pytest.raises(SourceUnavailableError, match="文件来源不可获取"):
        await use_case.execute(GetFileThumbnailQuery(file_id="file-1", size="list"))
    assert file.access_state == "available"


@pytest.mark.asyncio
async def test_reports_unknown_files(tmp_path: Path):
    use_case = GetFileThumbnailUseCase(
        FakeFileRepository(None),
        ThumbnailGenerator(),
        ThumbnailCache(tmp_path / "cache"),
        FakeSourceResolver(),
    )

    with pytest.raises(FileNotFoundError):
        await use_case.execute(GetFileThumbnailQuery(file_id="missing", size="list"))
