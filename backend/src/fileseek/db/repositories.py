"""Data access for files, video segments and document chunks.

Business logic depends on these repositories rather than on SQL, so the storage
details stay in one place. Batch lookups pass ids as a JSON array and expand them
with json_each, which keeps every statement a literal and sidesteps SQLite's
bound-variable ceiling.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence

from fileseek.db.records import (
    ChunkRecord,
    DocumentRecord,
    FileRecord,
    ImageRecord,
    IndexState,
    SegmentRecord,
    VideoRecord,
)

_SELECT_FILE = """
SELECT id, path, filename, media_type, size, content_hash,
       created_at, added_at, modified_at, index_state
FROM files
"""

_SELECT_SEGMENT = """
SELECT id, video_id, start_time, end_time, vector_id, thumbnail_rel_path
FROM video_segments
"""

_SELECT_CHUNK = """
SELECT id, file_id, chunk_index, char_start, char_end, vector_id
FROM doc_chunks
"""

_INSERT_FILE = """
INSERT INTO files (id, path, filename, media_type, size, content_hash,
                   created_at, added_at, modified_at, index_state)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

_INSERT_ORIGIN = """
INSERT INTO file_origins (file_id, original_path, recorded_at) VALUES (?, ?, ?)
ON CONFLICT (file_id, original_path) DO NOTHING
"""

_INSERT_SEGMENT = """
INSERT INTO video_segments (id, video_id, start_time, end_time, vector_id, thumbnail_rel_path)
VALUES (?, ?, ?, ?, ?, ?)
"""

_INSERT_CHUNK = """
INSERT INTO doc_chunks (id, file_id, chunk_index, char_start, char_end, vector_id)
VALUES (?, ?, ?, ?, ?, ?)
"""

_FILES_BY_IDS = """
SELECT id, path, filename, media_type, size, content_hash,
       created_at, added_at, modified_at, index_state
FROM files
WHERE id IN (SELECT value FROM json_each(?))
"""

_SEGMENTS_BY_VECTORS = """
SELECT id, video_id, start_time, end_time, vector_id, thumbnail_rel_path
FROM video_segments
WHERE vector_id IN (SELECT value FROM json_each(?))
"""

_CHUNKS_BY_VECTORS = """
SELECT id, file_id, chunk_index, char_start, char_end, vector_id
FROM doc_chunks
WHERE vector_id IN (SELECT value FROM json_each(?))
"""

# Vectors whose file is no longer searchable. Search filters these out by id, and
# a purge later removes them from the index for real.
_IMAGE_VECTORS_BY_STATE = """
SELECT images.vector_id AS vector_id
FROM images
JOIN files ON files.id = images.file_id
WHERE images.vector_id IS NOT NULL
  AND files.index_state IN (SELECT value FROM json_each(?))
"""

_CHUNK_VECTORS_BY_STATE = """
SELECT doc_chunks.vector_id AS vector_id
FROM doc_chunks
JOIN files ON files.id = doc_chunks.file_id
WHERE doc_chunks.vector_id IS NOT NULL
  AND files.index_state IN (SELECT value FROM json_each(?))
"""

_SEGMENT_VECTORS_BY_STATE = """
SELECT video_segments.vector_id AS vector_id
FROM video_segments
JOIN files ON files.id = video_segments.video_id
WHERE video_segments.vector_id IS NOT NULL
  AND files.index_state IN (SELECT value FROM json_each(?))
"""


def _media_type_query(
    select: str, media_type: str, index_states: Sequence[IndexState] | None
) -> tuple[str, list[object]]:
    sql = f"{select} WHERE media_type = ?"
    params: list[object] = [media_type]
    if index_states:
        sql += " AND index_state IN (SELECT value FROM json_each(?))"
        params.append(json.dumps(list(index_states)))
    return sql, params


def _to_file(row: sqlite3.Row) -> FileRecord:
    return FileRecord(
        id=row["id"],
        path=row["path"],
        filename=row["filename"],
        media_type=row["media_type"],
        size=row["size"],
        content_hash=row["content_hash"],
        added_at=row["added_at"],
        created_at=row["created_at"],
        modified_at=row["modified_at"],
        index_state=row["index_state"],
    )


def _to_segment(row: sqlite3.Row) -> SegmentRecord:
    return SegmentRecord(
        id=row["id"],
        video_id=row["video_id"],
        start_time=row["start_time"],
        end_time=row["end_time"],
        vector_id=row["vector_id"],
        thumbnail_rel_path=row["thumbnail_rel_path"],
    )


def _to_chunk(row: sqlite3.Row) -> ChunkRecord:
    return ChunkRecord(
        id=row["id"],
        file_id=row["file_id"],
        chunk_index=row["chunk_index"],
        char_start=row["char_start"],
        char_end=row["char_end"],
        vector_id=row["vector_id"],
    )


class FileRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def add(self, record: FileRecord, original_path: str | None = None) -> FileRecord:
        self._connection.execute(
            _INSERT_FILE,
            (
                record.id,
                record.path,
                record.filename,
                record.media_type,
                record.size,
                record.content_hash,
                record.created_at,
                record.added_at,
                record.modified_at,
                record.index_state,
            ),
        )
        if original_path is not None:
            self.add_origin(record.id, original_path, recorded_at=record.added_at)
        return record

    def add_origin(self, file_id: str, original_path: str, recorded_at: int) -> None:
        """Record where a file came from; re-submitting the same path is a no-op."""
        self._connection.execute(_INSERT_ORIGIN, (file_id, original_path, recorded_at))

    def origins(self, file_id: str) -> list[str]:
        rows = self._connection.execute(
            "SELECT original_path FROM file_origins WHERE file_id = ? ORDER BY id",
            (file_id,),
        ).fetchall()
        return [row["original_path"] for row in rows]

    def get(self, file_id: str) -> FileRecord | None:
        row = self._connection.execute(f"{_SELECT_FILE} WHERE id = ?", (file_id,)).fetchone()
        return None if row is None else _to_file(row)

    def get_by_content_hash(self, content_hash: str) -> FileRecord | None:
        row = self._connection.execute(
            f"{_SELECT_FILE} WHERE content_hash = ?", (content_hash,)
        ).fetchone()
        return None if row is None else _to_file(row)

    def get_by_path(self, path: str) -> FileRecord | None:
        row = self._connection.execute(f"{_SELECT_FILE} WHERE path = ?", (path,)).fetchone()
        return None if row is None else _to_file(row)

    def get_many(self, file_ids: Sequence[str]) -> list[FileRecord]:
        """Fetch several files at once, preserving the caller's id order."""
        if not file_ids:
            return []
        rows = self._connection.execute(_FILES_BY_IDS, (json.dumps(list(file_ids)),)).fetchall()
        found = {row["id"]: _to_file(row) for row in rows}
        return [found[file_id] for file_id in file_ids if file_id in found]

    def list_by_media_type(
        self,
        media_type: str,
        limit: int | None = 100,
        index_states: Sequence[IndexState] | None = None,
    ) -> list[FileRecord]:
        """Files of one kind, newest first.

        `limit=None` returns everything, which is what a rebuild needs: it must
        walk the whole library, not a page of it.
        """
        sql, params = _media_type_query(_SELECT_FILE, media_type, index_states)
        sql += " ORDER BY added_at DESC"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        rows = self._connection.execute(sql, params).fetchall()
        return [_to_file(row) for row in rows]

    def count_by_media_type(
        self, media_type: str, index_states: Sequence[IndexState] | None = None
    ) -> int:
        sql, params = _media_type_query("SELECT count(*) AS n FROM files", media_type, index_states)
        row = self._connection.execute(sql, params).fetchone()
        return int(row["n"])

    def list_by_index_state(self, index_state: IndexState) -> list[FileRecord]:
        rows = self._connection.execute(
            f"{_SELECT_FILE} WHERE index_state = ? ORDER BY added_at", (index_state,)
        ).fetchall()
        return [_to_file(row) for row in rows]

    def set_index_state(self, file_id: str, index_state: IndexState) -> bool:
        cursor = self._connection.execute(
            "UPDATE files SET index_state = ? WHERE id = ?", (index_state, file_id)
        )
        return cursor.rowcount > 0

    def delete(self, file_id: str) -> bool:
        cursor = self._connection.execute("DELETE FROM files WHERE id = ?", (file_id,))
        return cursor.rowcount > 0

    def count(self) -> int:
        row = self._connection.execute("SELECT count(*) AS n FROM files").fetchone()
        return int(row["n"])


class SegmentRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def add_many(self, segments: Sequence[SegmentRecord]) -> int:
        self._connection.executemany(
            _INSERT_SEGMENT,
            [
                (
                    segment.id,
                    segment.video_id,
                    segment.start_time,
                    segment.end_time,
                    segment.vector_id,
                    segment.thumbnail_rel_path,
                )
                for segment in segments
            ],
        )
        return len(segments)

    def get(self, segment_id: str) -> SegmentRecord | None:
        row = self._connection.execute(f"{_SELECT_SEGMENT} WHERE id = ?", (segment_id,)).fetchone()
        return None if row is None else _to_segment(row)

    def list_for_video(self, video_id: str) -> list[SegmentRecord]:
        """Segments in playback order, which is how results are presented."""
        rows = self._connection.execute(
            f"{_SELECT_SEGMENT} WHERE video_id = ? ORDER BY start_time", (video_id,)
        ).fetchall()
        return [_to_segment(row) for row in rows]

    def get_by_vector_ids(self, vector_ids: Sequence[int]) -> list[SegmentRecord]:
        if not vector_ids:
            return []
        rows = self._connection.execute(
            _SEGMENTS_BY_VECTORS, (json.dumps(list(vector_ids)),)
        ).fetchall()
        found = {row["vector_id"]: _to_segment(row) for row in rows}
        return [found[vector_id] for vector_id in vector_ids if vector_id in found]

    def vector_ids_by_state(self, index_states: Sequence[IndexState]) -> list[int]:
        """Segment vectors whose video is in one of these states."""
        if not index_states:
            return []
        rows = self._connection.execute(
            _SEGMENT_VECTORS_BY_STATE, (json.dumps(list(index_states)),)
        ).fetchall()
        return [row["vector_id"] for row in rows]

    def vector_ids_for_videos(self, video_ids: Sequence[str]) -> list[int]:
        """The vectors belonging to these videos, for removal from the index."""
        if not video_ids:
            return []
        rows = self._connection.execute(
            "SELECT vector_id FROM video_segments "
            "JOIN json_each(?) AS wanted ON video_segments.video_id = wanted.value "
            "WHERE vector_id IS NOT NULL",
            (json.dumps(list(video_ids)),),
        ).fetchall()
        return [row["vector_id"] for row in rows]

    def delete_for_video(self, video_id: str) -> int:
        cursor = self._connection.execute(
            "DELETE FROM video_segments WHERE video_id = ?", (video_id,)
        )
        return cursor.rowcount


class ChunkRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def add_many(self, chunks: Sequence[ChunkRecord]) -> int:
        self._connection.executemany(
            _INSERT_CHUNK,
            [
                (
                    chunk.id,
                    chunk.file_id,
                    chunk.chunk_index,
                    chunk.char_start,
                    chunk.char_end,
                    chunk.vector_id,
                )
                for chunk in chunks
            ],
        )
        return len(chunks)

    def get(self, chunk_id: str) -> ChunkRecord | None:
        row = self._connection.execute(f"{_SELECT_CHUNK} WHERE id = ?", (chunk_id,)).fetchone()
        return None if row is None else _to_chunk(row)

    def list_for_file(self, file_id: str) -> list[ChunkRecord]:
        """Chunks in document order so a hit maps back to its character range."""
        rows = self._connection.execute(
            f"{_SELECT_CHUNK} WHERE file_id = ? ORDER BY chunk_index", (file_id,)
        ).fetchall()
        return [_to_chunk(row) for row in rows]

    def get_by_vector_ids(self, vector_ids: Sequence[int]) -> list[ChunkRecord]:
        if not vector_ids:
            return []
        rows = self._connection.execute(
            _CHUNKS_BY_VECTORS, (json.dumps(list(vector_ids)),)
        ).fetchall()
        found = {row["vector_id"]: _to_chunk(row) for row in rows}
        return [found[vector_id] for vector_id in vector_ids if vector_id in found]

    def vector_ids_by_state(self, index_states: Sequence[IndexState]) -> list[int]:
        """Chunk vectors whose file is in one of these states."""
        if not index_states:
            return []
        rows = self._connection.execute(
            _CHUNK_VECTORS_BY_STATE, (json.dumps(list(index_states)),)
        ).fetchall()
        return [row["vector_id"] for row in rows]

    def vector_ids_for_files(self, file_ids: Sequence[str]) -> list[int]:
        """The vectors belonging to these files, for removal from the index."""
        if not file_ids:
            return []
        rows = self._connection.execute(
            "SELECT vector_id FROM doc_chunks "
            "JOIN json_each(?) AS wanted ON doc_chunks.file_id = wanted.value "
            "WHERE vector_id IS NOT NULL",
            (json.dumps(list(file_ids)),),
        ).fetchall()
        return [row["vector_id"] for row in rows]

    def delete_for_file(self, file_id: str) -> int:
        cursor = self._connection.execute("DELETE FROM doc_chunks WHERE file_id = ?", (file_id,))
        return cursor.rowcount


def _to_image(row: sqlite3.Row) -> ImageRecord:
    return ImageRecord(
        file_id=row["file_id"],
        width=row["width"],
        height=row["height"],
        ocr_text=row["ocr_text"],
        vector_id=row["vector_id"],
    )


class ImageRepository:
    """Per-image metadata: dimensions, recognised text, and its vector id."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def upsert(self, record: ImageRecord) -> None:
        """Write the row, replacing any earlier attempt for the same file.

        Upsert rather than insert because a reindex re-runs this for a file that
        already has a row.
        """
        self._connection.execute(
            "INSERT INTO images (file_id, width, height, ocr_text, vector_id) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT (file_id) DO UPDATE SET "
            "width = excluded.width, height = excluded.height, "
            "ocr_text = excluded.ocr_text, vector_id = excluded.vector_id",
            (
                record.file_id,
                record.width,
                record.height,
                record.ocr_text,
                record.vector_id,
            ),
        )

    def get(self, file_id: str) -> ImageRecord | None:
        row = self._connection.execute(
            "SELECT * FROM images WHERE file_id = ?", (file_id,)
        ).fetchone()
        return None if row is None else _to_image(row)

    def by_vector_ids(self, vector_ids: Sequence[int]) -> list[ImageRecord]:
        """Resolve search hits back to images, preserving the ranking order."""
        if not vector_ids:
            return []
        rows = self._connection.execute(
            "SELECT images.* FROM images "
            "JOIN json_each(?) AS wanted ON images.vector_id = wanted.value",
            (json.dumps(list(vector_ids)),),
        ).fetchall()
        found = {row["vector_id"]: _to_image(row) for row in rows}
        return [found[vector_id] for vector_id in vector_ids if vector_id in found]

    def vector_ids_for_files(self, file_ids: Sequence[str]) -> list[int]:
        """The vectors belonging to these files, for removal from the index."""
        if not file_ids:
            return []
        rows = self._connection.execute(
            "SELECT vector_id FROM images "
            "JOIN json_each(?) AS wanted ON images.file_id = wanted.value "
            "WHERE vector_id IS NOT NULL",
            (json.dumps(list(file_ids)),),
        ).fetchall()
        return [row["vector_id"] for row in rows]

    def vector_ids_by_state(self, index_states: Sequence[IndexState]) -> list[int]:
        """Vectors whose file is in one of these states, for search exclusion."""
        if not index_states:
            return []
        rows = self._connection.execute(
            _IMAGE_VECTORS_BY_STATE, (json.dumps(list(index_states)),)
        ).fetchall()
        return [row["vector_id"] for row in rows]

    def delete_for_file(self, file_id: str) -> int:
        cursor = self._connection.execute("DELETE FROM images WHERE file_id = ?", (file_id,))
        return cursor.rowcount


def _to_document(row: sqlite3.Row) -> DocumentRecord:
    return DocumentRecord(
        file_id=row["file_id"],
        text_content=row["text_content"],
        page_count=row["page_count"],
        language=row["language"],
        chunk_count=row["chunk_count"],
        text_source=row["text_source"],
    )


class DocumentRepository:
    """Per-document metadata; the chunks themselves live in ChunkRepository."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def upsert(self, record: DocumentRecord) -> None:
        self._connection.execute(
            "INSERT INTO documents "
            "(file_id, text_content, page_count, language, chunk_count, text_source) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT (file_id) DO UPDATE SET "
            "text_content = excluded.text_content, page_count = excluded.page_count, "
            "language = excluded.language, chunk_count = excluded.chunk_count, "
            "text_source = excluded.text_source",
            (
                record.file_id,
                record.text_content,
                record.page_count,
                record.language,
                record.chunk_count,
                record.text_source,
            ),
        )

    def get(self, file_id: str) -> DocumentRecord | None:
        row = self._connection.execute(
            "SELECT * FROM documents WHERE file_id = ?", (file_id,)
        ).fetchone()
        return None if row is None else _to_document(row)

    def delete_for_file(self, file_id: str) -> int:
        cursor = self._connection.execute("DELETE FROM documents WHERE file_id = ?", (file_id,))
        return cursor.rowcount


def _to_video(row: sqlite3.Row) -> VideoRecord:
    return VideoRecord(
        file_id=row["file_id"],
        duration=row["duration"],
        width=row["width"],
        height=row["height"],
        fps=row["fps"],
        sampled_frames=row["sampled_frames"],
    )


class VideoRepository:
    """Per-video metadata; the searchable segments live in SegmentRepository."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def upsert(self, record: VideoRecord) -> None:
        self._connection.execute(
            "INSERT INTO videos (file_id, duration, width, height, fps, sampled_frames) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT (file_id) DO UPDATE SET "
            "duration = excluded.duration, width = excluded.width, "
            "height = excluded.height, fps = excluded.fps, "
            "sampled_frames = excluded.sampled_frames",
            (
                record.file_id,
                record.duration,
                record.width,
                record.height,
                record.fps,
                record.sampled_frames,
            ),
        )

    def get(self, file_id: str) -> VideoRecord | None:
        row = self._connection.execute(
            "SELECT * FROM videos WHERE file_id = ?", (file_id,)
        ).fetchone()
        return None if row is None else _to_video(row)

    def delete_for_file(self, file_id: str) -> int:
        cursor = self._connection.execute("DELETE FROM videos WHERE file_id = ?", (file_id,))
        return cursor.rowcount
