from __future__ import annotations

import queue
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import cast

import pytest

from fileseek.features.library.domain.entities import File, FileChunk
from fileseek.features.library.domain.repositories import (
    FileChunkRepository,
    FileRepository,
)
from fileseek.features.tasks.application.cancellation import (
    TaskCancellationRegistry,
)
from fileseek.features.tasks.application.manager import DefaultTaskManager
from fileseek.features.tasks.application.processor import TaskProcessor
from fileseek.features.tasks.application.progress_reporter import (
    QueueProgressReporter,
)
from fileseek.features.tasks.application.scheduler import TaskScheduler
from fileseek.features.tasks.domain.entities import (
    Task,
    TaskProgress,
    TaskStage,
    TaskStatus,
)
from fileseek.features.tasks.domain.exceptions import (
    InvalidTransitionError,
    TaskCancelledError,
)
from fileseek.features.tasks.domain.repositories import TaskRepository
from fileseek.shared.domain.file_types import FileCategory, FileType
from fileseek.shared.utils.cache import TTLLRUCache


def _make_task(task_id: str = "task-1") -> Task:
    file = File(
        id="file-1",
        name="document.txt",
        file_type=FileType.TXT,
        category=FileCategory.DOCUMENT,
        size=1,
        modified=datetime.now(UTC),
        path="/source/document.txt",
        storage_id="local",
    )


    file.chunks.append(
        FileChunk(
            id=f"{task_id}_0",
            file_id=file.id,
        )
    )
    return Task(
        id=task_id,
        file=file,
        metadata={"temp_path": "cache.txt"},
        status=TaskStatus.PROCESSING,
    )


@pytest.mark.asyncio
async def test_cancel_task_marks_processing_task_cancelled() -> None:
    registry = TaskCancellationRegistry()
    task = _make_task("task-processing")

    class FakeTaskRepository:
        async def get_by_id(self, task_id: str) -> Task | None:
            return task if task_id == task.id else None

        async def cancel(self, task_id: str) -> Task | None:
            if task_id != task.id or task.status is not TaskStatus.PROCESSING:
                return None
            task.mark_cancelled()
            return task

    manager = DefaultTaskManager(
        cast(TaskRepository, FakeTaskRepository()),
        registry,
    )

    task = await manager.cancel("task-processing")

    assert task.status is TaskStatus.CANCELLED
    assert task.error_message == "任务已终止"
    assert registry.is_cancelled("task-processing")


@pytest.mark.asyncio
async def test_cancel_task_rejects_non_processing_task() -> None:
    registry = TaskCancellationRegistry()
    task = _make_task("task-queued")
    task.status = TaskStatus.QUEUED

    class FakeTaskRepository:
        async def get_by_id(self, task_id: str) -> Task | None:
            return task if task_id == task.id else None

        async def cancel(self, task_id: str) -> Task | None:
            _ = task_id
            return None

    manager = DefaultTaskManager(
        cast(TaskRepository, FakeTaskRepository()),
        registry,
    )

    with pytest.raises(InvalidTransitionError):
        await manager.cancel("task-queued")

    assert registry.is_cancelled("task-queued") is False


def test_progress_reporter_raises_when_task_cancelled() -> None:
    registry = TaskCancellationRegistry()
    registry.request("task-1")
    reporter = QueueProgressReporter(queue.Queue(), registry, "task-1")

    with pytest.raises(TaskCancelledError):
        reporter.report(
            TaskStage.EXTRACTED,
            completed_count=0,
            total_count=1,
        )


@pytest.mark.parametrize(
    ("completed_count", "total_count"),
    [
        (-1, 1),
        (2, 0),
        (2, 1),
    ],
)
def test_progress_reporter_rejects_invalid_count_pairs(
    completed_count: int,
    total_count: int,
) -> None:
    reporter = QueueProgressReporter(queue.Queue())

    with pytest.raises(ValueError):
        reporter.report(
            TaskStage.EXTRACTED,
            completed_count=completed_count,
            total_count=total_count,
        )


@pytest.mark.asyncio
async def test_scheduler_stops_task_and_skips_partial_persistence() -> None:
    registry = TaskCancellationRegistry()
    task = _make_task()
    saved_tasks: list[Task] = []

    class FakeTaskRepository:
        async def save(self, saved_task: Task) -> None:
            saved_tasks.append(saved_task)

    class FakeFileRepository:
        saved = False

        async def save(self, file: File) -> None:
            _ = file
            self.saved = True

    class FakeFileChunkRepository:
        saved = False

        async def save_batch(self, chunks: Sequence[FileChunk]) -> None:
            _ = chunks
            self.saved = True

    class FakeCache:
        async def clear(self, namespace: str) -> None:
            _ = namespace

    class FakeProcessor:
        cleaned_ids: list[str] = []

        def process(
            self,
            task: Task,
            progress_queue: queue.Queue[TaskProgress],
        ) -> None:
            registry.request(task.id)
            reporter = QueueProgressReporter(progress_queue, registry, task.id)
            reporter.report(
                TaskStage.EXTRACTED,
                completed_count=0,
                total_count=1,
            )

        def cleanup(self, task: Task) -> None:
            self.cleaned_ids.extend(chunk.id for chunk in task.file.chunks)

    file_repo = FakeFileRepository()
    chunk_repo = FakeFileChunkRepository()
    processor = FakeProcessor()
    scheduler = TaskScheduler(
        task_repo=cast(TaskRepository, FakeTaskRepository()),
        file_repo=cast(FileRepository, file_repo),
        file_chunk_repo=cast(FileChunkRepository, chunk_repo),
        processor=cast(TaskProcessor, processor),
        poll_interval=0.01,
        max_workers=1,
        cache=cast(TTLLRUCache[str, object], FakeCache()),
        cancellation_registry=registry,
    )

    try:
        await scheduler._execute_task(task)
    finally:
        scheduler._executor.shutdown(wait=False)

    assert task.status is TaskStatus.CANCELLED
    assert saved_tasks == [task]
    assert file_repo.saved is False
    assert chunk_repo.saved is False
    assert processor.cleaned_ids == ["task-1_0"]
    assert registry.is_cancelled("task-1") is False
