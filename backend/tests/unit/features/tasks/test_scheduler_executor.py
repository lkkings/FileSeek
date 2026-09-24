"""调度器把任务派发到执行器这条路径的回归测试。

针对的故障：执行器一度是 `ProcessPoolExecutor`，而派发的是
`processor.process` 这个绑定方法。进程池要 pickle 它，于是连带整个
`TaskProcessor` 一起序列化——它持有的 `EmbeddingService` / `OCRService`
各有一个 `threading.Lock` 用于模型懒加载互斥，锁不可 pickle，每个任务
都在派发那一刻就死于 `TypeError: cannot pickle '_thread.lock' object`。

所以这里验的是"处理器带着不可 pickle 的东西也必须能被派发"，而不是
执行器的具体类名：换回任何需要 pickle 入参的执行器，这些用例都会红。
"""

from __future__ import annotations

import multiprocessing as mp
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import AsyncMock, MagicMock

import pytest

from fileseek.features.tasks.application.scheduler import TaskScheduler
from fileseek.features.tasks.domain.entities import Task, TaskStatus
from fileseek.features.tasks.domain.repositories import TaskRepository


class UnpicklableProcessor:
    """带 threading.Lock 的处理器替身。

    锁是真的：它就是原故障里导致 pickle 失败的那个东西，换成别的哨兵
    就测不到这个 bug 了。
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.processed: list[str] = []

    def process(self, task: Task, progress_queue: mp.Queue) -> None:
        with self._lock:
            self.processed.append(task.id)


def _task(task_id: str = "t_1") -> Task:
    return Task(
        id=task_id,
        source_path="/seeded/a.pdf",
        status=TaskStatus.PROCESSING,
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
    )


def _scheduler(processor: UnpicklableProcessor) -> tuple[TaskScheduler, MagicMock]:
    repo = MagicMock(spec=TaskRepository)
    repo.save = AsyncMock()
    repo.claim_next_queued = AsyncMock(return_value=None)
    repo.list_all = AsyncMock(return_value=([], 0))
    return TaskScheduler(task_repo=repo, processor=processor), repo


def test_processor_holding_a_lock_is_not_pickled_for_dispatch() -> None:
    """锁本身不可 pickle——这是故障的前提，先把它钉住。"""
    import pickle

    processor = UnpicklableProcessor()

    with pytest.raises((TypeError, AttributeError)):
        pickle.dumps(processor.process)


@pytest.mark.asyncio
async def test_execute_task_dispatches_processor_holding_a_lock() -> None:
    """带锁的处理器能被正常派发并跑完，不会死在序列化上。"""
    processor = UnpicklableProcessor()
    scheduler, repo = _scheduler(processor)
    task = _task()

    await scheduler._execute_task(task)

    assert processor.processed == ["t_1"]
    # 跑通了就该落到终态，而不是被 mark_failed 记下一条 pickle 报错。
    assert task.status is TaskStatus.COMPLETED
    assert task.error_message is None
    repo.save.assert_awaited()


@pytest.mark.asyncio
async def test_execute_task_runs_in_a_thread_not_a_subprocess() -> None:
    """处理器和调度器必须在同一个进程里。

    进程池下子进程推进的是任务对象的副本，进度永远回不到父进程；
    共享内存里的这个列表也就不会被填上。
    """
    import os

    seen: list[int] = []

    class PidRecordingProcessor(UnpicklableProcessor):
        def process(self, task: Task, progress_queue: mp.Queue) -> None:
            seen.append(os.getpid())

    scheduler, _ = _scheduler(PidRecordingProcessor())

    await scheduler._execute_task(_task())

    assert seen == [os.getpid()]


def test_executor_does_not_require_picklable_arguments() -> None:
    """执行器本身就是线程池，不对入参做序列化。"""
    processor = UnpicklableProcessor()
    scheduler, _ = _scheduler(processor)

    assert isinstance(scheduler._executor, ThreadPoolExecutor)
