"""Turns a source path into a library file, or recognises it as a duplicate.

Content is hashed before anything moves, so a file already in the library costs
one read and no write.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from fileseek.db.records import FileRecord, MediaType
from fileseek.db.repositories import FileRepository
from fileseek.library.hashing import CHUNK_SIZE, hash_file
from fileseek.library.layout import LibraryLayout
from fileseek.library.mover import MoveResult, SourceMissingError, move_into_library
from fileseek.media_types import media_type_for


@dataclass(frozen=True)
class IngestOutcome:
    record: FileRecord
    was_duplicate: bool
    moved: MoveResult | None = None


class UnsupportedMediaError(ValueError):
    def __init__(self, source: Path) -> None:
        super().__init__(f"unsupported file type: {source.name}")
        self.source = source


def _now() -> int:
    return int(time.time())


def _stat_times(source: Path) -> tuple[int | None, int | None]:
    try:
        info = source.stat()
    except OSError:
        return None, None
    return int(info.st_ctime), int(info.st_mtime)


def ingest_file(
    source: Path,
    layout: LibraryLayout,
    files: FileRepository,
    chunk_size: int = CHUNK_SIZE,
    media_type: MediaType | None = None,
) -> IngestOutcome:
    """Move source into the library, or record another origin for a known duplicate."""
    if not source.is_file():
        raise SourceMissingError(source)

    resolved_type = media_type if media_type is not None else media_type_for(source)
    if resolved_type is None:
        raise UnsupportedMediaError(source)

    content_hash = hash_file(source, chunk_size)
    existing = files.get_by_content_hash(content_hash)
    if existing is not None:
        # Same bytes already in the library: keep one copy, remember where this
        # submission came from, and leave the caller's file where it is.
        files.add_origin(existing.id, str(source), recorded_at=_now())
        return IngestOutcome(record=existing, was_duplicate=True)

    destination = layout.allocate_path(resolved_type, source.name)
    created_at, modified_at = _stat_times(source)
    moved = move_into_library(source, destination, chunk_size, known_hash=content_hash)

    record = FileRecord(
        id=str(uuid.uuid4()),
        path=str(moved.destination),
        filename=moved.destination.name,
        media_type=resolved_type,
        size=moved.size,
        content_hash=moved.content_hash,
        added_at=_now(),
        created_at=created_at,
        modified_at=modified_at,
        index_state="pending",
    )
    files.add(record, original_path=str(source))
    return IngestOutcome(record=record, was_duplicate=False, moved=moved)
