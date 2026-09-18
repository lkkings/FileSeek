"""Runs one claimed task through the pipeline for its media type.

The outcome is recorded on the task rather than raised: a file that cannot be
decoded must leave a failed task carrying a readable reason the UI can show, not
an unhandled traceback, and never a task stranded in `processing`.

Failing costs no data. Ingest moves the file into the library before anything
reads its content, so a decode failure leaves the file safely in place and the
task can be retried once the cause is fixed.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from fileseek.db.records import FileRecord, MediaType
from fileseek.media_types import media_type_for
from fileseek.pipeline.context import IndexingContext, ProgressReporter, QueueProgress
from fileseek.pipeline.documents import index_document
from fileseek.pipeline.images import index_image
from fileseek.tasks.queue import TaskQueue
from fileseek.tasks.records import TaskRecord

# What a pipeline raises for input it cannot handle: an unreadable image, a
# vanished source, an unsupported type. Anything outside this set is a bug rather
# than bad input, so it is left to propagate instead of being filed as a failure.
PIPELINE_ERRORS = (OSError, RuntimeError, ValueError)

# The DB column is a plain string; this maps it back onto the literal type.
_MEDIA_TYPES: dict[str, MediaType] = {
    "document": "document",
    "image": "image",
    "video": "video",
}


class IndexedResult(Protocol):
    """What the runner needs back from any pipeline: the file it indexed."""

    @property
    def record(self) -> FileRecord: ...


# Ingests and indexes one file. Video joins this table when its pipeline lands;
# until then those tasks fail with a readable reason rather than being silently
# dropped.
Handler = Callable[[Path, IndexingContext, ProgressReporter], IndexedResult]

_HANDLERS: dict[MediaType, Handler] = {"document": index_document, "image": index_image}


@dataclass(frozen=True)
class TaskOutcome:
    task: TaskRecord
    file_id: str | None = None
    error: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.error is None

    def describe(self) -> str:
        if self.succeeded:
            return f"indexed {Path(self.task.source_path).name}"
        return f"{Path(self.task.source_path).name} failed: {self.error}"


def _fail(queue: TaskQueue, task: TaskRecord, reason: str) -> TaskOutcome:
    return TaskOutcome(task=queue.mark_failed(task.id, reason), error=reason)


def _resolve_media_type(task: TaskRecord, source: Path) -> MediaType | None:
    """Trust the task's recorded type, falling back to the file's extension."""
    if task.media_type is not None:
        return _MEDIA_TYPES.get(task.media_type)
    return media_type_for(source)


def run_task(
    task: TaskRecord,
    queue: TaskQueue,
    context: IndexingContext,
    handlers: Mapping[MediaType, Handler] | None = None,
) -> TaskOutcome:
    """Index the task's file, recording completion or failure on the task.

    The task is expected to be claimed already, so this only reports the outcome
    of the work itself.
    """
    table = handlers if handlers is not None else _HANDLERS
    source = Path(task.source_path)

    media_type = _resolve_media_type(task, source)
    handler = table.get(media_type) if media_type is not None else None
    if handler is None:
        return _fail(queue, task, f"unsupported file type: {source.name}")

    try:
        result = handler(source, context, QueueProgress(queue, task.id))
    except PIPELINE_ERRORS as error:
        # The message names the file and what went wrong, which is what the task
        # view shows next to the retry button.
        return _fail(queue, task, str(error))

    file_id = result.record.id
    return TaskOutcome(task=queue.mark_completed(task.id, file_id=file_id), file_id=file_id)
