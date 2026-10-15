from __future__ import annotations

import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import cast

import pytest

from fileseek.features.library.domain.entities import File, FileChunk
from fileseek.features.library.domain.repositories import (
    FileChunkRepository,
    FileRepository,
)
from fileseek.features.tasks.application.cancellation import TaskCancellationRegistry
from fileseek.features.tasks.application.compute import TaskSpec
from fileseek.features.tasks.application.manager import DefaultTaskManager
from fileseek.features.tasks.application.processor import TaskProcessor
from fileseek.features.tasks.application.scheduler import TaskScheduler
from fileseek.features.tasks.domain.entities import Task, TaskStatus
from fileseek.features.tasks.domain.repositories import TaskRepository
from fileseek.shared.domain.file_types import FileCategory, FileType
from fileseek.shared.utils.cache import TTLLRUCache


def _make_task(task_id: str) -> Task:
    file = File(
        id=f"file-{task_id}",
        name="document.txt",
        file_type=FileType.TXT,
        category=FileCategory.DOCUMENT,
        size=1,
        modified=datetime.now(UTC),
        path="/source/document.txt",
        storage_id="local",
    )
    return Task(
        id=task_id,
        file=file,
        metadata={},
        status=TaskStatus.PROCESSING,
    )


class FakeTaskRepository:
    def __init__(self, task: Task) -> None:
        self.task = task
        self.status = task.status

    async def save(self, task: Task) -> None:
        self.task = task
        self.status = task.status

    async def list_all(self, status, page, page_size):
        _ = status, page, page_size
        return [], 0

    async def claim_next_queued(self):
        return None

    async def cancel_incomplete(self) -> tuple[int, tuple[str, ...]]:
        self.status = TaskStatus.CANCELLED
        return 1, (self.task.id,)

    async def continue_cancelled(self) -> int:
        self.status = TaskStatus.QUEUED
        return 1


@pytest.mark.asyncio
async def test_cancellation_signal_before_scheduler_start_cannot_overwrite_continued_task() -> None:
    task = _make_task("task-processing")
    registry = TaskCancellationRegistry()
    task_repo = FakeTaskRepository(task)
    manager = DefaultTaskManager(cast(TaskRepository, task_repo), registry)

    class FakeFileRepository:
        async def save(self, file: File) -> None:
            _ = file

    class FakeFileChunkRepository:
        async def save_batch(self, chunks: Sequence[FileChunk]) -> None:
            _ = chunks

    class FakeCache:
        async def clear(self, namespace: str) -> None:
            _ = namespace

    class FakeProcessor:
        @staticmethod
        def build_spec(task: Task) -> TaskSpec:
            return TaskProcessor.build_spec(task)

        def cleanup(self, task: Task) -> None:
            _ = task

    class FakeCompute:
        terminated = False

        def in_cooldown(self) -> bool:
            return False

        def submit(self, spec: TaskSpec) -> None:
            _ = spec

        def poll(self) -> object | None:
            return None

        def terminate(self) -> None:
            self.terminated = True

        def shutdown(self) -> None:
            pass

    compute = FakeCompute()
    scheduler = TaskScheduler(
        task_repo=cast(TaskRepository, task_repo),
        file_repo=cast(FileRepository, FakeFileRepository()),
        file_chunk_repo=cast(FileChunkRepository, FakeFileChunkRepository()),
        processor=cast(TaskProcessor, FakeProcessor()),
        compute=cast(object(), compute),
        poll_interval=0.01,
        cache=cast(TTLLRUCache[str, object], FakeCache()),
        cancellation_registry=registry,
    )

    await manager.cancel_incomplete()
    scheduler_task = asyncio.create_task(scheduler._execute_task(task))
    await manager.continue_cancelled()
    await scheduler_task

    assert task_repo.status is TaskStatus.QUEUED
    assert registry.pending_ids() == ()
