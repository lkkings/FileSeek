import sqlite3
from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest

from fileseek.db import (
    ChunkRepository,
    DocumentRepository,
    FileRepository,
    ImageRepository,
    SegmentRepository,
    VideoRepository,
    connect,
    migrate,
)
from fileseek.extract.documents import UnreadableDocumentError
from fileseek.index.registry import IndexRegistry
from fileseek.library.layout import LibraryLayout
from fileseek.models.tiers import CPU_BUNDLE
from fileseek.models.vectors import is_normalized, normalize
from fileseek.pipeline.context import IndexingContext
from fileseek.pipeline.documents import index_document, reindex_document
from fileseek.tasks.records import STAGE_ORDER, Stage

from doc_fixtures import write_docx, write_encrypted_pdf, write_pdf

TEXT_WIDTH = CPU_BUNDLE.text_dimensions

# Long enough to split into several chunks, so chunk handling is exercised.
LONG_TEXT = (
    "Retrieval augmented generation combines a search index with a language model. "
    "The index supplies passages and the model conditions its answer on them. "
) * 40


class WordVectorEncoder:
    """Vectors seeded by which keywords a passage contains.

    Not semantics, but enough that a query sharing a keyword with a chunk lands
    nearest it, which is what the index wiring has to get right. The genuine
    semantic claim is checked separately against the real weights.
    """

    VOCABULARY = ("retrieval", "kitten", "budget", "深度学习")

    def __init__(self, recognized: str = "") -> None:
        self.recognized = recognized
        self.recognized_pages = 0
        self.encoded_batches: list[int] = []

    def _vector(self, text: str) -> list[float]:
        lowered = text.lower()
        raw = [0.05] * TEXT_WIDTH
        for position, word in enumerate(self.VOCABULARY):
            if word in lowered:
                raw[position] = 1.0
        return normalize(raw)

    def encode_images(self, images: Sequence[bytes]) -> list[list[float]]:
        return [normalize([1.0] + [0.0] * (CPU_BUNDLE.image_dimensions - 1)) for _ in images]

    def encode_texts(self, texts: Sequence[str]) -> list[list[float]]:
        self.encoded_batches.append(len(texts))
        return [self._vector(text) for text in texts]

    def recognize_text(self, image: bytes) -> str:  # noqa: ARG002 - fixed reply
        self.recognized_pages += 1
        return self.recognized


class RecordingProgress:
    def __init__(self) -> None:
        self.completed: list[Stage] = []

    def report(self, stage: Stage, percent: int) -> None:
        return None

    def stage_done(self, stage: Stage) -> None:
        self.completed.append(stage)


@pytest.fixture
def db() -> Iterator[sqlite3.Connection]:
    connection = connect(":memory:")
    migrate(connection)
    yield connection
    connection.close()


@pytest.fixture
def encoder() -> WordVectorEncoder:
    return WordVectorEncoder()


def make_context(
    tmp_path: Path, db: sqlite3.Connection, encoder: WordVectorEncoder
) -> IndexingContext:
    return IndexingContext(
        layout=LibraryLayout(root=tmp_path / "library").initialize(),
        files=FileRepository(db),
        images=ImageRepository(db),
        documents=DocumentRepository(db),
        videos=VideoRepository(db),
        segments=SegmentRepository(db),
        chunks=ChunkRepository(db),
        registry=IndexRegistry(tmp_path / "index", db, CPU_BUNDLE),
        encoder=encoder,
    )


@pytest.fixture
def context(tmp_path: Path, db: sqlite3.Connection, encoder: WordVectorEncoder) -> IndexingContext:
    return make_context(tmp_path, db, encoder)


@pytest.fixture
def incoming(tmp_path: Path) -> Path:
    directory = tmp_path / "downloads"
    directory.mkdir()
    return directory


def write_text_file(directory: Path, name: str = "notes.txt", body: str = LONG_TEXT) -> Path:
    path = directory / name
    path.write_text(body, encoding="utf-8")
    return path


# --- 8.3: the ingest pipeline -----------------------------------------------


def test_the_document_is_moved_into_the_library(context: IndexingContext, incoming: Path) -> None:
    source = write_text_file(incoming)

    result = index_document(source, context)

    assert Path(result.record.path).parent == context.layout.media_dir("document")
    assert Path(result.record.path).is_file()
    assert not source.exists()


def test_the_extracted_text_is_recorded(context: IndexingContext, incoming: Path) -> None:
    """Stored text is what lets a result show the passage that matched."""
    result = index_document(write_text_file(incoming), context)

    stored = context.documents.get(result.record.id)
    assert stored is not None
    assert stored.text_content is not None
    assert "Retrieval augmented generation" in stored.text_content


def test_a_long_document_is_split_into_several_chunks(
    context: IndexingContext, incoming: Path
) -> None:
    """Chunking rather than truncation is what keeps later pages searchable."""
    result = index_document(write_text_file(incoming), context)

    assert result.chunk_count > 1
    assert len(context.chunks.list_for_file(result.record.id)) == result.chunk_count


def test_every_chunk_lands_in_the_document_index(context: IndexingContext, incoming: Path) -> None:
    result = index_document(write_text_file(incoming), context)

    assert context.registry.open("document").size == result.chunk_count
    assert len(result.vector_ids) == result.chunk_count


def test_chunks_keep_their_order_and_ranges(context: IndexingContext, incoming: Path) -> None:
    result = index_document(write_text_file(incoming), context)

    chunks = context.chunks.list_for_file(result.record.id)

    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))
    assert all(chunk.char_end > chunk.char_start for chunk in chunks)


def test_a_topic_query_finds_the_document(context: IndexingContext, incoming: Path) -> None:
    """The end-to-end claim: a natural-language query reaches the right file."""
    result = index_document(write_text_file(incoming), context)
    query = context.encoder.encode_texts(["retrieval"])[0]

    hits = context.registry.search("document", query, limit=5)

    matched = context.chunks.get_by_vector_ids([hit.vector_id for hit in hits])
    assert matched
    assert matched[0].file_id == result.record.id


def test_an_unrelated_query_does_not_reach_it(context: IndexingContext, incoming: Path) -> None:
    index_document(write_text_file(incoming), context)
    query = context.encoder.encode_texts(["kitten"])[0]

    hits = context.registry.search("document", query, limit=1)

    assert hits[0].score < 0.9


def test_the_document_joins_full_text_search(
    context: IndexingContext, incoming: Path, db: sqlite3.Connection
) -> None:
    """Literal matches have to work too, not only vector similarity."""
    result = index_document(write_text_file(incoming), context)

    rows = db.execute(
        "SELECT documents.file_id FROM documents_fts "
        "JOIN documents ON documents.rowid = documents_fts.rowid "
        "WHERE documents_fts MATCH ?",
        ("augmented",),
    ).fetchall()

    assert [row["file_id"] for row in rows] == [result.record.id]


def test_the_file_is_marked_indexed(context: IndexingContext, incoming: Path) -> None:
    result = index_document(write_text_file(incoming), context)

    stored = context.files.get(result.record.id)
    assert stored is not None
    assert stored.index_state == "indexed"


def test_the_index_is_persisted(context: IndexingContext, incoming: Path) -> None:
    index_document(write_text_file(incoming), context)

    assert context.registry.path_for("document").is_file()


def test_stored_vectors_are_normalized(context: IndexingContext, incoming: Path) -> None:
    result = index_document(write_text_file(incoming), context)

    stored = context.registry.open("document").reconstruct(result.vector_ids[0])
    assert stored is not None
    assert is_normalized(stored, tolerance=1e-5)


def test_the_stages_are_reported_in_order(context: IndexingContext, incoming: Path) -> None:
    progress = RecordingProgress()

    index_document(write_text_file(incoming), context, progress)

    assert progress.completed == list(STAGE_ORDER)


def test_a_pdf_records_its_page_count(context: IndexingContext, incoming: Path) -> None:
    source = write_pdf(incoming / "paper.pdf", ["Retrieval methods", "Second page"])

    result = index_document(source, context)

    assert result.page_count == 2


def test_a_docx_is_indexed(context: IndexingContext, incoming: Path) -> None:
    source = write_docx(incoming / "memo.docx", ["Retrieval augmented generation notes"] * 20)

    result = index_document(source, context)

    assert result.chunk_count >= 1
    assert result.text_source == "embedded"


def test_a_duplicate_is_not_indexed_twice(context: IndexingContext, incoming: Path) -> None:
    first = index_document(write_text_file(incoming, name="notes.txt"), context)
    nested = incoming / "again"
    nested.mkdir()

    second = index_document(write_text_file(nested, name="copy.txt"), context)

    assert second.was_duplicate is True
    assert second.record.id == first.record.id
    assert context.registry.open("document").size == first.chunk_count


def test_a_duplicate_reports_what_was_stored(context: IndexingContext, incoming: Path) -> None:
    first = index_document(write_text_file(incoming, name="notes.txt"), context)
    nested = incoming / "again"
    nested.mkdir()

    second = index_document(write_text_file(nested, name="copy.txt"), context)

    assert second.chunk_count == first.chunk_count
    assert second.vector_ids == first.vector_ids


def test_a_duplicate_of_an_unindexed_file_reports_nothing_stored(
    context: IndexingContext, incoming: Path
) -> None:
    from fileseek.library.ingest import ingest_file

    first = ingest_file(write_text_file(incoming, name="notes.txt"), context.layout, context.files)
    nested = incoming / "again"
    nested.mkdir()

    result = index_document(write_text_file(nested, name="copy.txt"), context)

    assert result.was_duplicate is True
    assert result.record.id == first.record.id
    assert result.chunk_count == 0


# --- 8.4: OCR fallback for a scan -------------------------------------------


def test_a_scan_falls_back_to_recognition(
    tmp_path: Path, db: sqlite3.Connection, incoming: Path
) -> None:
    """A PDF with no text layer has to be read as pixels instead."""
    encoder = WordVectorEncoder(recognized="Retrieval augmented generation, scanned")
    context = make_context(tmp_path, db, encoder)
    source = write_pdf(incoming / "scan.pdf", ["", ""])

    result = index_document(source, context)

    assert result.used_recognition
    assert encoder.recognized_pages > 0


def test_a_recognized_scan_is_searchable_by_content(
    tmp_path: Path, db: sqlite3.Connection, incoming: Path
) -> None:
    encoder = WordVectorEncoder(recognized="Retrieval augmented generation, scanned")
    context = make_context(tmp_path, db, encoder)
    source = write_pdf(incoming / "scan.pdf", ["", ""])

    result = index_document(source, context)

    assert result.is_searchable_by_content
    query = encoder.encode_texts(["retrieval"])[0]
    hits = context.registry.search("document", query, limit=3)
    matched = context.chunks.get_by_vector_ids([hit.vector_id for hit in hits])
    assert matched[0].file_id == result.record.id


def test_recognized_text_is_stored_as_the_document_text(
    tmp_path: Path, db: sqlite3.Connection, incoming: Path
) -> None:
    encoder = WordVectorEncoder(recognized="Retrieval augmented generation, scanned")
    context = make_context(tmp_path, db, encoder)

    result = index_document(write_pdf(incoming / "scan.pdf", [""]), context)

    stored = context.documents.get(result.record.id)
    assert stored is not None
    assert stored.text_source == "ocr"
    assert "scanned" in (stored.text_content or "")


def test_a_scan_with_no_recognizable_text_is_name_only(
    tmp_path: Path, db: sqlite3.Connection, incoming: Path
) -> None:
    """Nothing to index is not a failure: the file stays and keeps its name."""
    context = make_context(tmp_path, db, WordVectorEncoder(recognized=""))
    source = write_pdf(incoming / "blank.pdf", ["", ""])

    result = index_document(source, context)

    assert result.is_searchable_by_content is False
    assert result.text_source == "none"
    assert Path(result.record.path).is_file()


def test_a_name_only_document_is_still_recorded(
    tmp_path: Path, db: sqlite3.Connection, incoming: Path
) -> None:
    context = make_context(tmp_path, db, WordVectorEncoder(recognized=""))

    result = index_document(write_pdf(incoming / "blank.pdf", [""]), context)

    stored = context.documents.get(result.record.id)
    assert stored is not None
    assert stored.chunk_count == 0
    assert stored.is_searchable_by_content is False
    assert context.registry.open("document").size == 0


def test_a_name_only_document_is_findable_by_filename(
    tmp_path: Path, db: sqlite3.Connection, incoming: Path
) -> None:
    context = make_context(tmp_path, db, WordVectorEncoder(recognized=""))
    result = index_document(write_pdf(incoming / "blank.pdf", [""]), context)

    rows = db.execute(
        "SELECT files.id FROM files_fts JOIN files ON files.rowid = files_fts.rowid "
        "WHERE files_fts MATCH ?",
        ("blank",),
    ).fetchall()

    assert [row["id"] for row in rows] == [result.record.id]


def test_a_document_with_text_never_reaches_recognition(
    context: IndexingContext, incoming: Path, encoder: WordVectorEncoder
) -> None:
    index_document(write_text_file(incoming), context)

    assert encoder.recognized_pages == 0


# --- 8.5: encrypted or corrupt documents ------------------------------------


def test_a_corrupt_pdf_fails_with_a_reason(context: IndexingContext, incoming: Path) -> None:
    source = incoming / "broken.pdf"
    source.write_bytes(b"%PDF-1.4 then garbage")

    with pytest.raises(UnreadableDocumentError, match="broken.pdf"):
        index_document(source, context)


def test_a_corrupt_document_stays_in_the_library(context: IndexingContext, incoming: Path) -> None:
    """The move happens before parsing, so a failure must not lose the bytes."""
    source = incoming / "broken.pdf"
    source.write_bytes(b"%PDF-1.4 then garbage")

    with pytest.raises(UnreadableDocumentError):
        index_document(source, context)

    assert (context.layout.media_dir("document") / "broken.pdf").is_file()
    assert not source.exists()


def test_a_corrupt_document_is_not_marked_indexed(context: IndexingContext, incoming: Path) -> None:
    source = incoming / "broken.pdf"
    source.write_bytes(b"%PDF-1.4 then garbage")

    with pytest.raises(UnreadableDocumentError):
        index_document(source, context)

    stored = context.files.get_by_path(str(context.layout.media_dir("document") / "broken.pdf"))
    assert stored is not None
    assert stored.index_state == "pending"


def test_a_corrupt_document_leaves_no_vectors(context: IndexingContext, incoming: Path) -> None:
    source = incoming / "broken.docx"
    source.write_bytes(b"not a zip container")

    with pytest.raises(UnreadableDocumentError):
        index_document(source, context)

    assert context.registry.open("document").size == 0


def test_an_encrypted_pdf_fails_with_a_reason(context: IndexingContext, incoming: Path) -> None:
    """A password-protected file cannot be read, and must say so rather than look empty."""
    source = write_encrypted_pdf(incoming / "locked.pdf", ["Confidential contents"])

    with pytest.raises(UnreadableDocumentError, match="password protected"):
        index_document(source, context)


def test_an_encrypted_pdf_stays_in_the_library(context: IndexingContext, incoming: Path) -> None:
    source = write_encrypted_pdf(incoming / "locked.pdf", ["Confidential contents"])

    with pytest.raises(UnreadableDocumentError):
        index_document(source, context)

    assert (context.layout.media_dir("document") / "locked.pdf").is_file()
    assert not source.exists()


def test_an_encrypted_pdf_is_not_marked_indexed(context: IndexingContext, incoming: Path) -> None:
    """It must not be mistaken for a scan with no text: nothing was read at all."""
    source = write_encrypted_pdf(incoming / "locked.pdf", ["Confidential contents"])

    with pytest.raises(UnreadableDocumentError):
        index_document(source, context)

    stored = context.files.get_by_path(str(context.layout.media_dir("document") / "locked.pdf"))
    assert stored is not None
    assert stored.index_state == "pending"
    assert context.documents.get(stored.id) is None


# --- reindexing -------------------------------------------------------------


def test_reindexing_replaces_the_previous_chunks(context: IndexingContext, incoming: Path) -> None:
    """Ids are never reused, so stale chunks would otherwise keep matching."""
    first = index_document(write_text_file(incoming), context)
    Path(first.record.path).write_text("A budget spreadsheet summary. " * 60, encoding="utf-8")

    result = reindex_document(first.record, context)

    assert set(result.vector_ids).isdisjoint(first.vector_ids)
    assert context.registry.open("document").size == result.chunk_count
    assert len(context.chunks.list_for_file(first.record.id)) == result.chunk_count


def test_reindexing_picks_up_the_new_content(context: IndexingContext, incoming: Path) -> None:
    first = index_document(write_text_file(incoming), context)
    Path(first.record.path).write_text("A budget spreadsheet summary. " * 60, encoding="utf-8")

    reindex_document(first.record, context)

    stored = context.documents.get(first.record.id)
    assert stored is not None
    assert "budget" in (stored.text_content or "")
    assert "Retrieval" not in (stored.text_content or "")


def test_reindexing_restores_the_indexed_state(context: IndexingContext, incoming: Path) -> None:
    first = index_document(write_text_file(incoming), context)
    context.files.set_index_state(first.record.id, "needs_reindex")

    reindex_document(first.record, context)

    stored = context.files.get(first.record.id)
    assert stored is not None
    assert stored.index_state == "indexed"


def test_reindexing_reports_every_stage(context: IndexingContext, incoming: Path) -> None:
    first = index_document(write_text_file(incoming), context)
    progress = RecordingProgress()

    reindex_document(first.record, context, progress)

    assert progress.completed == list(STAGE_ORDER)
