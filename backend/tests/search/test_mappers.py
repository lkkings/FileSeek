from datetime import UTC, datetime

from fileseek.features.library.domain.entities import File, FileChunk
from fileseek.features.search.application.mappers import file_to_dto
from fileseek.shared.domain.file_types import FileCategory, FileType


def _file(chunks):
    return File(
        id="file-1",
        name="pending.pdf",
        file_type=FileType.PDF,
        category=FileCategory.DOCUMENT,
        size=100,
        modified=datetime(2026, 9, 29, tzinfo=UTC),
        path="/library/pending.pdf",
        chunks=chunks,
    )


def test_file_to_dto_defaults_empty_chunks_to_an_empty_list() -> None:
    dto = file_to_dto(_file([]))

    assert dto.chunks == []
    assert dto.score == 0
    assert dto.metadata == {}


def test_file_to_dto_handles_missing_chunks() -> None:
    dto = file_to_dto(_file(None))

    assert dto.chunks == []
    assert dto.score == 0
    assert dto.metadata == {}


def test_file_to_dto_uses_the_highest_scoring_chunk() -> None:
    chunks = [
        FileChunk(id="chunk-1", file_id="file-1", score=0.2, metadata={"page": 1}),
        FileChunk(id="chunk-2", file_id="file-1", score=0.8, metadata={"page": 2}),
    ]

    dto = file_to_dto(_file(chunks))

    assert dto.chunks == chunks
    assert dto.score == 0.8
    assert dto.metadata == {"page": 2}
