"""导入计算跑在真实子进程里时的调度行为：结果落库、崩溃隔离、终止、崩溃后续跑。"""

from __future__ import annotations

import os
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest
from tests.tasks.worker_targets import fake_task_worker

from fileseek.features.library.domain.entities import File, FileChunk
from fileseek.features.library.domain.repositories import FileChunkRepository, FileRepository
from fileseek.features.tasks.application.cancellation import TaskCancellationRegistry
from fileseek.features.tasks.application.processor import TaskProcessor
from fileseek.features.tasks.application.scheduler import TaskScheduler
from fileseek.features.tasks.domain.entities import Task, TaskStage, TaskStatus
from fileseek.features.tasks.domain.repositories import TaskRepository
from fileseek.features.tasks.infrastructure.worker import TaskWorkerClient
from fileseek.shared.domain.file_types import FileCategory, FileType
from fileseek.shared.infrastructure.worker import WorkerHandle
from fileseek.shared.utils.cache import TTLLRUCache


class _TaskRepo:
    def __init__(self) -> None:
        self.saved: list[tuple[str, TaskStatus, TaskStage | None]] = []

    async def save(self, task: Task) -> None:
        self.saved.append((task.id, task.status, task.stage))


class _FileRepo:
    def __init__(self) -> None:
        self.saved: list[str] = []

    async def save(self, file: File) -> None:
        self.saved.append(file.id)


class _ChunkRepo:
    def __init__(self) -> None:
        self.saved: list[str] = []

    async def save_batch(self, chunks: Sequence[FileChunk]) -> None:
        self.saved.extend(chunk.id for chunk in chunks)


class _VectorIndex:
    def __init__(self) -> None:
        self.ids: list[str] = []
        self.deleted: list[str] = []

    def add_batch(self, ids, vectors) -> None:
        self.ids.extend(ids)

    def delete_batch(self, ids) -> None:
        self.deleted.extend(ids)


class _Cache:
    async def clear(self, namespace: str) -> None:
        _ = namespace


def _task(tmp_path: Path, task_id: str, content: str) -> Task:
    cache = tmp_path / f"{task_id}.txt"
    cache.write_text(content, encoding="utf-8")
    file = File(
        id=f"file-{task_id}",
        name=f"{task_id}.txt",
        file_type=FileType.TXT,
        category=FileCategory.DOCUMENT,
        size=1,
        modified=datetime.now(UTC),
        path=f"/source/{task_id}.txt",
        storage_id="local",
    )
    return Task(
        id=task_id,
        file=file,
        metadata={"temp_path": str(cache)},
        status=TaskStatus.PROCESSING,
    )


@pytest.fixture
def harness():
    registry = TaskCancellationRegistry()
    task_repo, file_repo = _TaskRepo(), _FileRepo()
    chunk_repo, index = _ChunkRepo(), _VectorIndex()
    compute = TaskWorkerClient(
        WorkerHandle("test-task-worker", fake_task_worker, {"idle_timeout": 0})
    )
    scheduler = TaskScheduler(
        task_repo=cast(TaskRepository, task_repo),
        file_repo=cast(FileRepository, file_repo),
        file_chunk_repo=cast(FileChunkRepository, chunk_repo),
        processor=TaskProcessor(vector_index=index),
        compute=compute,
        poll_interval=0.01,
        cache=cast(TTLLRUCache[str, object], _Cache()),
        cancellation_registry=registry,
    )
    yield scheduler, compute, registry, task_repo, file_repo, chunk_repo, index
    compute.shutdown()


@pytest.mark.asyncio
async def test_task_is_computed_in_subprocess_and_persisted(harness, tmp_path: Path) -> None:
    scheduler, compute, _, task_repo, file_repo, chunk_repo, index = harness
    task = _task(tmp_path, "ok", "a\nb\nc\n")

    await scheduler._execute_task(task)

    assert task.status is TaskStatus.COMPLETED, task.error_message
    assert compute.handle.pid not in (None, os.getpid())
    assert index.ids == ["file-ok_0", "file-ok_1", "file-ok_2"]
    assert [chunk.metadata for chunk in task.file.chunks] == [
        {"text": "a"},
        {"text": "b"},
        {"text": "c"},
    ]
    assert task.file.tags == ["note"]
    assert file_repo.saved == ["file-ok"]
    assert chunk_repo.saved == ["file-ok_0", "file-ok_1", "file-ok_2"]
    # 进度从子进程一路推进到服务进程写入阶段
    stages = [stage for _, _, stage in task_repo.saved]
    assert TaskStage.ENCODED in stages
    assert stages[-1] is TaskStage.INDEXED
    # 临时文件由子进程处理完删掉
    assert not (tmp_path / "ok.txt").exists()


@pytest.mark.asyncio
async def test_python_error_in_subprocess_fails_task_only(harness, tmp_path: Path) -> None:
    scheduler, compute, *_ = harness
    task = _task(tmp_path, "bad", "fail")

    await scheduler._execute_task(task)

    assert task.status is TaskStatus.FAILED
    assert task.error_message == "无法解析"
    assert compute.handle.is_alive()


@pytest.mark.asyncio
async def test_crash_fails_task_and_next_task_succeeds(harness, tmp_path: Path) -> None:
    scheduler, compute, _, _, _, _, index = harness
    crashing = _task(tmp_path, "crash", "sigkill")
    following = _task(tmp_path, "next", "x\ny\n")

    await scheduler._execute_task(crashing)

    assert crashing.status is TaskStatus.FAILED
    assert "SIGKILL" in (crashing.error_message or "")
    assert not (tmp_path / "crash.txt").exists()

    await scheduler._execute_task(following)

    assert following.status is TaskStatus.COMPLETED, following.error_message
    assert index.ids == ["file-next_0", "file-next_1"]


@pytest.mark.asyncio
async def test_shutdown_puts_a_task_still_computing_back_in_the_queue(
    harness, tmp_path: Path
) -> None:
    """drain 超时仍在算的任务放回 queued，而不是停在 processing 等人推进。"""
    import asyncio

    scheduler, compute, *_ = harness
    stuck = _task(tmp_path, "stuck", "sleep")
    stuck.status = TaskStatus.QUEUED

    class _QueueRepo(_TaskRepo):
        async def claim_next_queued(self) -> Task | None:
            if stuck.status is not TaskStatus.QUEUED:
                return None
            stuck.status = TaskStatus.PROCESSING
            return stuck

        async def list_all(self, status, page, page_size):
            _ = page, page_size
            matching = [stuck] if stuck.status is status else []
            return matching, len(matching)

    scheduler.task_repo = cast(TaskRepository, _QueueRepo())
    scheduler.start()
    deadline = time.monotonic() + 10
    while not (scheduler.active_count and compute.handle.is_alive()):
        assert time.monotonic() < deadline, "任务没有开始计算"
        await asyncio.sleep(0.05)

    released = await scheduler.shutdown(timeout=0.5)

    assert released == ("stuck",)
    assert stuck.status is TaskStatus.QUEUED
    assert not compute.handle.is_alive()


@pytest.mark.asyncio
async def test_cancel_terminates_long_running_compute(harness, tmp_path: Path) -> None:
    scheduler, compute, registry, _, file_repo, _, index = harness
    stuck = _task(tmp_path, "stuck", "sleep")
    following = _task(tmp_path, "after", "z\n")

    import asyncio

    async def cancel_soon() -> None:
        await asyncio.sleep(1.5)
        registry.request(stuck.id)

    started = time.monotonic()
    await asyncio.gather(scheduler._execute_task(stuck), cancel_soon())

    assert time.monotonic() - started < 1.5 + 5
    assert stuck.status is TaskStatus.CANCELLED
    assert file_repo.saved == []
    assert not compute.handle.is_alive()

    await scheduler._execute_task(following)

    assert following.status is TaskStatus.COMPLETED, following.error_message
    assert index.ids == ["file-after_0"]
