"""Takes an image from a path outside the library to a searchable entry.

Moves the file in, encodes its pixels, recognises any text shown in it, and
records both so the picture is findable by description and by the words it
contains.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fileseek.db.records import FileRecord, ImageRecord
from fileseek.extract.images import (
    DEFAULT_MAX_EDGE,
    ImageMetadata,
    load_for_encoding,
    read_metadata,
)
from fileseek.library.ingest import IngestOutcome, ingest_file
from fileseek.pipeline.context import IndexingContext, NullProgress, ProgressReporter

# Recognition reads whatever text is shown in the picture, so it needs far more
# detail than the encoder: a screenshot shrunk to 512px is illegible.
OCR_MAX_EDGE = 1600


@dataclass(frozen=True)
class ImageIndexed:
    record: FileRecord
    was_duplicate: bool
    # Absent for a duplicate that was never indexed: there is nothing to report
    # yet, and inventing zeros would read as real dimensions.
    metadata: ImageMetadata | None = None
    vector_id: int | None = None
    recognized_text: str = ""

    @property
    def has_recognized_text(self) -> bool:
        return bool(self.recognized_text.strip())

    @property
    def is_searchable(self) -> bool:
        return self.vector_id is not None


def index_image(
    source: Path,
    context: IndexingContext,
    progress: ProgressReporter | None = None,
) -> ImageIndexed:
    """Ingest and index one image, reporting progress as each stage completes."""
    reporter = progress if progress is not None else NullProgress()

    outcome: IngestOutcome = ingest_file(source, context.layout, context.files, media_type="image")
    record = outcome.record
    reporter.stage_done("moved")

    if outcome.was_duplicate:
        # These bytes are already in the library; ingest recorded the new origin and
        # there is nothing to encode again. Report what the earlier pass stored.
        existing = context.images.get(record.id)
        if existing is None:
            return ImageIndexed(record=record, was_duplicate=True)
        return ImageIndexed(
            record=record,
            was_duplicate=True,
            metadata=ImageMetadata(
                width=existing.width,
                height=existing.height,
                image_format=Path(record.path).suffix.lstrip(".").lower(),
            ),
            vector_id=existing.vector_id,
            recognized_text=existing.ocr_text or "",
        )

    return _encode_and_store(record, context, reporter, was_duplicate=False)


def reindex_image(
    record: FileRecord,
    context: IndexingContext,
    progress: ProgressReporter | None = None,
) -> ImageIndexed:
    """Re-encode a library image whose content changed underneath us.

    Reached from the consistency scan, which marks a replaced file needs_reindex.
    Ingestion is skipped: the file is already in the library, and its old vector
    describes content that is gone.
    """
    reporter = progress if progress is not None else NullProgress()
    reporter.stage_done("moved")
    return _encode_and_store(record, context, reporter, was_duplicate=False)


def _encode_and_store(
    record: FileRecord,
    context: IndexingContext,
    reporter: ProgressReporter,
    was_duplicate: bool,
) -> ImageIndexed:
    path = Path(record.path)
    metadata = read_metadata(path)
    payload = load_for_encoding(path, max_edge=DEFAULT_MAX_EDGE)
    reporter.stage_done("extracted")

    vector = context.encoder.encode_images([payload])[0]
    recognized = context.encoder.recognize_text(load_for_encoding(path, max_edge=OCR_MAX_EDGE))
    reporter.stage_done("encoded")

    # Drop any earlier vector first: ids are never reused, so a stale entry would
    # otherwise keep matching content the file no longer has.
    previous = context.images.get(record.id)
    if previous is not None and previous.vector_id is not None:
        context.registry.remove("image", [previous.vector_id])

    vector_id = context.registry.allocate_ids("image", 1)[0]
    context.registry.add("image", [vector_id], [vector])
    context.images.upsert(
        ImageRecord(
            file_id=record.id,
            width=metadata.width,
            height=metadata.height,
            ocr_text=recognized or None,
            vector_id=vector_id,
        )
    )
    context.files.set_index_state(record.id, "indexed")
    context.registry.save("image")
    reporter.stage_done("indexed")

    return ImageIndexed(
        record=record,
        metadata=metadata,
        vector_id=vector_id,
        recognized_text=recognized,
        was_duplicate=was_duplicate,
    )
