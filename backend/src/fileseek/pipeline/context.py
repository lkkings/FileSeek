"""What an indexing pipeline needs, and how it reports progress.

The encoder is a Protocol rather than a concrete worker handle so a pipeline can
be tested without loading gigabytes of model weights, and so the same code runs
against either tier.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from fileseek.db.repositories import (
    ChunkRepository,
    DocumentRepository,
    FileRepository,
    ImageRepository,
    SegmentRepository,
    VideoRepository,
)
from fileseek.index.registry import IndexRegistry
from fileseek.library.layout import LibraryLayout
from fileseek.tasks.records import Stage


class Encoder(Protocol):
    """The encoding calls the pipelines make, satisfied by the model worker."""

    def encode_images(self, images: Sequence[bytes]) -> list[list[float]]: ...

    def encode_texts(self, texts: Sequence[str]) -> list[list[float]]: ...

    def recognize_text(self, image: bytes) -> str: ...


class ProgressReporter(Protocol):
    """Where stage and percentage updates go, so the UI can follow along."""

    def report(self, stage: Stage, percent: int) -> None: ...

    def stage_done(self, stage: Stage) -> None: ...


class NullProgress:
    """Discards progress, for callers that only want the result."""

    def report(self, stage: Stage, percent: int) -> None:  # noqa: ARG002 - null object
        return None

    def stage_done(self, stage: Stage) -> None:  # noqa: ARG002 - null object
        return None


class ProgressSink(Protocol):
    """The task-queue calls a reporter makes."""

    def report_progress(self, task_id: str, percent: int, stage: Stage | None = ...) -> object: ...

    def complete_stage(self, task_id: str, stage: Stage) -> object: ...


class QueueProgress:
    """Forwards progress to a task, so it survives a restart and reaches the UI."""

    def __init__(self, queue: ProgressSink, task_id: str) -> None:
        self._queue = queue
        self._task_id = task_id

    def report(self, stage: Stage, percent: int) -> None:
        self._queue.report_progress(self._task_id, percent, stage=stage)

    def stage_done(self, stage: Stage) -> None:
        self._queue.complete_stage(self._task_id, stage)


@dataclass(frozen=True)
class IndexingContext:
    """The collaborators every media pipeline writes through."""

    layout: LibraryLayout
    files: FileRepository
    images: ImageRepository
    documents: DocumentRepository
    videos: VideoRepository
    segments: SegmentRepository
    chunks: ChunkRepository
    registry: IndexRegistry
    encoder: Encoder
