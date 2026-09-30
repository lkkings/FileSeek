from __future__ import annotations

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
from fileseek.features.tasks.application.compute import TaskSpec
from fileseek.features.tasks.application.progress_reporter import (
    CallbackProgressReporter,
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
    reporter = CallbackProgressReporter(lambda progress: None)

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

        @staticmethod
        def build_spec(task: Task) -> TaskSpec:
            return TaskProcessor.build_spec(task)

        def persist(self, task, result, progress) -> None:
            raise AssertionError("被终止的任务不应写入")

        def cleanup(self, task: Task) -> None:
            self.cleaned_ids.extend(chunk.id for chunk in task.file.chunks)

    class FakeCompute:
        """第一次 poll 时模拟用户点了终止；之后一直没有结果（计算卡在长推理里）。"""

        terminated = False

        def in_cooldown(self) -> bool:
            return False

        def submit(self, spec: TaskSpec) -> None:
            _ = spec

        def poll(self) -> object | None:
            registry.request(task.id)
            return TaskProgress(TaskStage.EXTRACTED, 0, 1)

        def terminate(self) -> None:
            self.terminated = True

        def shutdown(self) -> None:
            pass

    file_repo = FakeFileRepository()
    chunk_repo = FakeFileChunkRepository()
    processor = FakeProcessor()
    compute = FakeCompute()
    scheduler = TaskScheduler(
        task_repo=cast(TaskRepository, FakeTaskRepository()),
        file_repo=cast(FileRepository, file_repo),
        file_chunk_repo=cast(FileChunkRepository, chunk_repo),
        processor=cast(TaskProcessor, processor),
        compute=compute,
        poll_interval=0.01,
        cache=cast(TTLLRUCache[str, object], FakeCache()),
        cancellation_registry=registry,
    )

    await scheduler._execute_task(task)

    assert compute.terminated is True
    assert task.status is TaskStatus.CANCELLED
    assert saved_tasks[-1] is task
    assert file_repo.saved is False
    assert chunk_repo.saved is False
    assert processor.cleaned_ids == ["task-1_0"]
    assert registry.is_cancelled("task-1") is False
