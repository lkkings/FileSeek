"""Row-shaped value objects returned by the repositories."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

MediaType = Literal["document", "image", "video"]
IndexState = Literal["pending", "indexed", "missing", "needs_reindex"]


@dataclass(frozen=True)
class FileRecord:
    id: str
    path: str
    filename: str
    media_type: MediaType
    size: int
    content_hash: str
    added_at: int
    created_at: int | None = None
    modified_at: int | None = None
    index_state: IndexState = "pending"


@dataclass(frozen=True)
class ImageRecord:
    file_id: str
    width: int
    height: int
    ocr_text: str | None = None
    vector_id: int | None = None

    @property
    def has_recognized_text(self) -> bool:
        return bool(self.ocr_text and self.ocr_text.strip())


@dataclass(frozen=True)
class DocumentRecord:
    file_id: str
    text_content: str | None = None
    page_count: int | None = None
    language: str | None = None
    chunk_count: int = 0
    text_source: str | None = None

    @property
    def is_searchable_by_content(self) -> bool:
        """False for a scan whose pages yielded no text, which is name-only."""
        return self.chunk_count > 0


@dataclass(frozen=True)
class VideoRecord:
    file_id: str
    duration: float
    width: int
    height: int
    fps: float | None = None
    sampled_frames: int = 0


@dataclass(frozen=True)
class SegmentRecord:
    id: str
    video_id: str
    start_time: float
    end_time: float
    vector_id: int | None = None
    thumbnail_rel_path: str | None = None

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time


@dataclass(frozen=True)
class ChunkRecord:
    id: str
    file_id: str
    chunk_index: int
    char_start: int
    char_end: int
    vector_id: int | None = None

    @property
    def length(self) -> int:
        return self.char_end - self.char_start
