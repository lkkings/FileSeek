"""Takes a document from a path outside the library to a searchable entry.

Moves the file in, reads its text, splits that text into chunks the encoder can
take whole, and records both the vectors and the text itself: the vectors answer
"what is this about", the stored text lets a result show the passage that matched.

A scan carries no text layer, so a PDF whose pages come back empty is rendered
and read by character recognition instead. When even that yields nothing the file
is kept and marked as findable by name only, rather than failed: the bytes are
in the library and nothing about them is wrong.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

from fileseek.db.records import ChunkRecord, DocumentRecord, FileRecord
from fileseek.extract.chunking import TextChunk, chunk_text
from fileseek.extract.documents import ExtractedText, extract_text, rasterize_pages
from fileseek.library.ingest import IngestOutcome, ingest_file
from fileseek.pipeline.context import IndexingContext, NullProgress, ProgressReporter

# Only a PDF can be rasterised for recognition; an empty .txt is simply empty.
_RASTERIZABLE = ".pdf"


@dataclass(frozen=True)
class DocumentIndexed:
    record: FileRecord
    was_duplicate: bool
    text: str = ""
    page_count: int | None = None
    chunk_count: int = 0
    text_source: str | None = None
    vector_ids: tuple[int, ...] = ()

    @property
    def is_searchable_by_content(self) -> bool:
        """False for a scan that yielded no text, which is findable by name only."""
        return self.chunk_count > 0

    @property
    def used_recognition(self) -> bool:
        return self.text_source == "ocr"


def index_document(
    source: Path,
    context: IndexingContext,
    progress: ProgressReporter | None = None,
) -> DocumentIndexed:
    """Ingest and index one document, reporting progress as each stage completes."""
    reporter = progress if progress is not None else NullProgress()

    outcome: IngestOutcome = ingest_file(
        source, context.layout, context.files, media_type="document"
    )
    record = outcome.record
    reporter.stage_done("moved")

    if outcome.was_duplicate:
        # These bytes are already in the library; ingest recorded the new origin and
        # there is nothing to read again. Report what the earlier pass stored.
        existing = context.documents.get(record.id)
        if existing is None:
            return DocumentIndexed(record=record, was_duplicate=True)
        return DocumentIndexed(
            record=record,
            was_duplicate=True,
            text=existing.text_content or "",
            page_count=existing.page_count,
            chunk_count=existing.chunk_count,
            text_source=existing.text_source,
            vector_ids=tuple(context.chunks.vector_ids_for_files([record.id])),
        )

    return _encode_and_store(record, context, reporter, was_duplicate=False)


def reindex_document(
    record: FileRecord,
    context: IndexingContext,
    progress: ProgressReporter | None = None,
) -> DocumentIndexed:
    """Re-read a library document whose content changed underneath us.

    Reached from the consistency scan and from an index rebuild. Ingestion is
    skipped: the file is already in the library, and its old chunks describe text
    that is gone.
    """
    reporter = progress if progress is not None else NullProgress()
    reporter.stage_done("moved")
    return _encode_and_store(record, context, reporter, was_duplicate=False)


def _recognize_pages(path: Path, context: IndexingContext, page_count: int | None) -> ExtractedText:
    """Read a scan's pages as pixels, since they carry no text layer."""
    pages = rasterize_pages(path)
    recognized = [context.encoder.recognize_text(page) for page in pages]
    joined = "\n".join(text.strip() for text in recognized if text.strip())
    # page_count comes from the PDF itself: rendering stops after the first pages,
    # so counting rendered images would under-report a long scan.
    return ExtractedText(text=joined, page_count=page_count, source="ocr")


def _read_text(path: Path, context: IndexingContext) -> ExtractedText:
    """The document's text, falling back to recognition for a scan."""
    extracted = extract_text(path)
    if extracted.has_text:
        return extracted

    if extracted.needs_ocr and path.suffix.lower() == _RASTERIZABLE:
        recognized = _recognize_pages(path, context, extracted.page_count)
        if recognized.has_text:
            return recognized

    # Nothing usable was found. The file keeps its place in the library and stays
    # findable by name; claiming empty content would be worse than saying so.
    return ExtractedText(text="", page_count=extracted.page_count, source="none")


def _drop_previous(record: FileRecord, context: IndexingContext) -> None:
    """Clear an earlier pass's chunks, so stale text cannot keep matching.

    Ids are never reused, so the old vectors have to leave the index explicitly.
    """
    previous = context.chunks.vector_ids_for_files([record.id])
    if previous:
        context.registry.remove("document", previous)
    context.chunks.delete_for_file(record.id)


def _store(
    record: FileRecord,
    context: IndexingContext,
    extracted: ExtractedText,
    chunks: list[TextChunk],
    vectors: list[list[float]],
) -> tuple[int, ...]:
    _drop_previous(record, context)

    # The document row lands first: chunks reference it, and writing text_content
    # is what puts the document into full-text search.
    context.documents.upsert(
        DocumentRecord(
            file_id=record.id,
            text_content=extracted.text or None,
            page_count=extracted.page_count,
            chunk_count=len(chunks),
            text_source=extracted.source,
        )
    )

    vector_ids = tuple(context.registry.allocate_ids("document", len(chunks)))
    if chunks:
        context.chunks.add_many(
            [
                ChunkRecord(
                    id=str(uuid.uuid4()),
                    file_id=record.id,
                    chunk_index=chunk.index,
                    char_start=chunk.char_start,
                    char_end=chunk.char_end,
                    vector_id=vector_id,
                )
                for chunk, vector_id in zip(chunks, vector_ids, strict=True)
            ]
        )
        context.registry.add("document", list(vector_ids), vectors)

    context.files.set_index_state(record.id, "indexed")
    context.registry.save("document")
    return vector_ids


def _encode_and_store(
    record: FileRecord,
    context: IndexingContext,
    reporter: ProgressReporter,
    was_duplicate: bool,
) -> DocumentIndexed:
    path = Path(record.path)
    extracted = _read_text(path, context)
    reporter.stage_done("extracted")

    chunks = chunk_text(extracted.text) if extracted.has_text else []
    vectors = context.encoder.encode_texts([chunk.text for chunk in chunks]) if chunks else []
    reporter.stage_done("encoded")

    vector_ids = _store(record, context, extracted, chunks, vectors)
    reporter.stage_done("indexed")

    return DocumentIndexed(
        record=record,
        was_duplicate=was_duplicate,
        text=extracted.text,
        page_count=extracted.page_count,
        chunk_count=len(chunks),
        text_source=extracted.source,
        vector_ids=vector_ids,
    )
