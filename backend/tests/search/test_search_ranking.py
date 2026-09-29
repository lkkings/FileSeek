from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from fileseek.features.library.domain.entities import File, FileChunk
from fileseek.features.search.application.queries import SearchFilesQuery
from fileseek.features.search.application.use_cases import SearchFilesUseCase
from fileseek.infrastructure.vector_store import VectorSearchResult
from fileseek.shared.domain.file_types import FileCategory, FileType


class _FakeEmbedder:
    def embed_text(
        self,
        texts: str | list[str],
        *,
        query: bool = False,
    ) -> list[list[float]]:
        return [[0.1]]


class _FakeVectorStore:
    def __init__(self, results: list[VectorSearchResult]) -> None:
        self._results = results

    def search(self, vector, *, ids=None, limit=-1, score_threshold=None):
        return self._results


def _image_file(file_id: str, chunks: list[FileChunk]) -> File:
    return File(
        id=file_id,
        name=f"{file_id}.png",
        file_type=FileType.PNG,
        category=FileCategory.IMAGE,
        size=100,
        modified=datetime(2026, 9, 29, tzinfo=UTC),
        path=f"/library/{file_id}.png",
        chunks=chunks,
    )


def _document_file(file_id: str, chunks: list[FileChunk]) -> File:
    return File(
        id=file_id,
        name=f"{file_id}.pdf",
        file_type=FileType.PDF,
        category=FileCategory.DOCUMENT,
        size=100,
        modified=datetime(2026, 9, 29, tzinfo=UTC),
        path=f"/library/{file_id}.pdf",
        chunks=chunks,
    )


async def _search(
    files: list[File],
    results: list[VectorSearchResult],
    categories: list[FileCategory] | None,
) -> list:
    embedder = _FakeEmbedder()
    vector_store = _FakeVectorStore(results)
    file_repo = AsyncMock()
    file_repo.query.return_value = files
    file_repo.count_by_category.return_value = {}
    cache = AsyncMock()
    cache.get.return_value = None

    use_case = SearchFilesUseCase(embedder, vector_store, file_repo, cache)
    request = SearchFilesQuery(
        query="sunset",
        tag=None,
        folder_id=None,
        categories=categories,
    )

    response = await use_case.execute(request)
    return response.items


@pytest.mark.asyncio
async def test_unfiltered_search_weights_text_lower_than_image() -> None:
    image_chunks = [
        FileChunk(
            id="image-visual",
            file_id="image-1",
            metadata={"feature_type": "image"},
        ),
        FileChunk(
            id="image-ocr",
            file_id="image-1",
            metadata={"feature_type": "ocr", "text": "sunset"},
        ),
    ]
    document_chunks = [
        FileChunk(
            id="document-text",
            file_id="document-1",
            metadata={"feature_type": "text"},
        ),
    ]
    image = _image_file("image-1", image_chunks)
    document = _document_file("document-1", document_chunks)
    results = [
        VectorSearchResult(id="image-visual", score=0.8),
        VectorSearchResult(id="image-ocr", score=0.9),
        VectorSearchResult(id="document-text", score=0.9),
    ]

    items = await _search([image, document], results, None)

    assert items[0].file_id == "image-1"
    assert items[0].score == pytest.approx(0.8)
    assert items[0].metadata["match_type"] == "image"
    assert items[0].metadata["raw_score"] == pytest.approx(0.8)
    assert items[1].file_id == "document-1"
    assert items[1].score == pytest.approx(0.54)
    assert "match_type" not in items[1].metadata


@pytest.mark.asyncio
async def test_image_only_search_weights_ocr_lower_than_image() -> None:
    image_chunks = [
        FileChunk(
            id="image-visual",
            file_id="image-1",
            metadata={"feature_type": "image"},
        ),
        FileChunk(
            id="image-ocr",
            file_id="image-1",
            metadata={"feature_type": "ocr", "text": "sunset"},
        ),
    ]
    ocr_only_chunks = [
        FileChunk(
            id="ocr-only",
            file_id="image-2",
            metadata={"feature_type": "ocr", "text": "sunset"},
        ),
    ]
    image = _image_file("image-1", image_chunks)
    ocr_only = _image_file("image-2", ocr_only_chunks)
    results = [
        VectorSearchResult(id="image-visual", score=0.8),
        VectorSearchResult(id="image-ocr", score=0.9),
        VectorSearchResult(id="ocr-only", score=0.9),
    ]

    items = await _search(
        [image, ocr_only],
        results,
        [FileCategory.IMAGE],
    )

    assert items[0].file_id == "image-1"
    assert items[0].score == pytest.approx(0.8)
    assert items[0].metadata["match_type"] == "image"
    assert items[1].file_id == "image-2"
    assert items[1].score == pytest.approx(0.36)
    assert items[1].metadata["match_type"] == "ocr"
    assert items[1].metadata["raw_score"] == pytest.approx(0.9)


@pytest.mark.asyncio
async def test_mixed_category_search_uses_unfiltered_text_weight() -> None:
    image_chunks = [
        FileChunk(
            id="image-visual",
            file_id="image-1",
            metadata={"feature_type": "image"},
        ),
    ]
    document_chunks = [
        FileChunk(
            id="document-text",
            file_id="document-1",
            metadata={"feature_type": "text"},
        ),
    ]
    image = _image_file("image-1", image_chunks)
    document = _document_file("document-1", document_chunks)
    results = [
        VectorSearchResult(id="image-visual", score=0.8),
        VectorSearchResult(id="document-text", score=0.9),
    ]

    items = await _search(
        [image, document],
        results,
        [FileCategory.IMAGE, FileCategory.DOCUMENT],
    )

    assert items[0].file_id == "image-1"
    assert items[0].score == pytest.approx(0.8)
    assert items[1].file_id == "document-1"
    assert items[1].score == pytest.approx(0.54)


@pytest.mark.asyncio
async def test_missing_image_feature_metadata_defaults_to_visual_match() -> None:
    chunks = [
        FileChunk(id="legacy-image", file_id="image-1", metadata=None),
    ]
    image = _image_file("image-1", chunks)
    results = [VectorSearchResult(id="legacy-image", score=0.7)]

    items = await _search([image], results, [FileCategory.IMAGE])

    assert items[0].file_id == "image-1"
    assert items[0].score == pytest.approx(0.7)
    assert items[0].metadata["match_type"] == "image"
    assert items[0].metadata["raw_score"] == pytest.approx(0.7)


@pytest.mark.asyncio
async def test_document_only_search_preserves_relative_order() -> None:
    first_chunks = [
        FileChunk(
            id="document-1-text",
            file_id="document-1",
            metadata={"feature_type": "text"},
        ),
    ]
    second_chunks = [
        FileChunk(
            id="document-2-text",
            file_id="document-2",
            metadata={"feature_type": "text"},
        ),
    ]
    first = _document_file("document-1", first_chunks)
    second = _document_file("document-2", second_chunks)
    results = [
        VectorSearchResult(id="document-1-text", score=0.9),
        VectorSearchResult(id="document-2-text", score=0.8),
    ]

    items = await _search(
        [first, second],
        results,
        [FileCategory.DOCUMENT],
    )

    assert [item.file_id for item in items] == ["document-1", "document-2"]
    assert items[0].score == pytest.approx(0.54)
    assert items[1].score == pytest.approx(0.48)
