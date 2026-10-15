from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import cast

import pytest

from fileseek.features.library.domain.entities import File, FileChunk
from fileseek.features.library.domain.repositories import (
    FileChunkRepository,
    FileRepository,
)
from fileseek.features.tasks.application.cancellation import TaskCancellationRegistry
from fileseek.features.tasks.application.manager import DefaultTaskManager
from fileseek.features.tasks.application.processor import TaskProcessor
from fileseek.features.tasks.application.scheduler import TaskScheduler
from fileseek.features.tasks.domain.exceptions import TaskCancellationPendingError
from fileseek.features.tasks.domain.repositories import TaskRepository
from fileseek.shared.utils.cache import TTLLRUCache


class FakeTaskRepository:
    def __init__(self) -> None:
        self.cancelled_count = 0
        self.continued_count = 0
        self.deleted_count = 0
        self.continue_called = False

    async def cancel_incomplete(self) -> tuple[int, tuple[str, ...]]:
        self.cancelled_count += 1
        return 3, ("processing-1",)

    async def continue_cancelled(self) -> int:
        self.continue_called = True
        self.continued_count += 1
        return 2

    async def delete_completed(self) -> int:
        self.deleted_count += 1
        return 4

    async def claim_next_queued(self):
        return None

    async def list_all(self, status, page, page_size):
        _ = status, page, page_size
        return [], 0


@pytest.mark.asyncio
async def test_manager_bulk_cancel_incomplete_requests_processing_cancellation() -> None:
    registry = TaskCancellationRegistry()
    repository = FakeTaskRepository()
    manager = DefaultTaskManager(cast(TaskRepository, repository), registry)

    count = await manager.cancel_incomplete()

    assert count == 3
    assert repository.cancelled_count == 1
    assert registry.pending_ids() == ("processing-1",)


@pytest.mark.asyncio
async def test_manager_continue_cancelled_waits_for_cleanup() -> None:
    registry = TaskCancellationRegistry()
    registry.request("processing-1")
    repository = FakeTaskRepository()
    manager = DefaultTaskManager(cast(TaskRepository, repository), registry)

    async def clear_cancellation_later() -> None:
        await asyncio.sleep(0.01)
        registry.clear("processing-1")

    clear_task = asyncio.create_task(clear_cancellation_later())
    count = await manager.continue_cancelled()
    await clear_task

    assert count == 2
    assert repository.continue_called is True
    assert registry.pending_ids() == ()


@pytest.mark.asyncio
async def test_manager_continue_cancelled_fails_when_cleanup_never_finishes() -> None:
    registry = TaskCancellationRegistry()
    registry.request("processing-1")
    repository = FakeTaskRepository()
    manager = DefaultTaskManager(cast(TaskRepository, repository), registry)
    manager.CANCELLATION_CLEANUP_TIMEOUT_SECONDS = 0.01

    with pytest.raises(TaskCancellationPendingError):
        await manager.continue_cancelled()

    assert repository.continue_called is False


@pytest.mark.asyncio
async def test_manager_delete_completed_delegates_to_repository() -> None:
    repository = FakeTaskRepository()
    manager = DefaultTaskManager(cast(TaskRepository, repository), TaskCancellationRegistry())

    count = await manager.delete_completed()

    assert count == 4
    assert repository.deleted_count == 1


@pytest.mark.asyncio
async def test_manager_bulk_operations_keep_scheduler_running() -> None:
    registry = TaskCancellationRegistry()
    repository = FakeTaskRepository()
    manager = DefaultTaskManager(cast(TaskRepository, repository), registry)

    class FakeFileRepository:
        async def save(self, file: File) -> None:
            _ = file

    class FakeFileChunkRepository:
        async def save_batch(self, chunks: Sequence[FileChunk]) -> None:
            _ = chunks

    class FakeCache:
        async def clear(self, namespace: str) -> None:
            _ = namespace

    class FakeCompute:
        def in_cooldown(self) -> bool:
            return False

        def shutdown(self) -> None:
            pass

    scheduler = TaskScheduler(
        task_repo=cast(TaskRepository, repository),
        file_repo=cast(FileRepository, FakeFileRepository()),
        file_chunk_repo=cast(FileChunkRepository, FakeFileChunkRepository()),
        processor=cast(TaskProcessor, object()),
        compute=cast(object(), FakeCompute()),
        poll_interval=0.01,
        cache=cast(TTLLRUCache[str, object], FakeCache()),
        cancellation_registry=registry,
    )
    scheduler.start()

    await manager.cancel_incomplete()
    assert scheduler.is_running is True
    assert scheduler._accepting is True

    registry.clear("processing-1")
    await manager.continue_cancelled()
    assert scheduler.is_running is True
    assert scheduler._accepting is True

    await scheduler.shutdown()
