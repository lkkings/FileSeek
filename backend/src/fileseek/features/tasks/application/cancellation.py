from __future__ import annotations

import threading
from functools import lru_cache


class TaskCancellationRegistry:
    """跨事件循环和工作线程共享的任务取消信号。"""

    def __init__(self) -> None:
        self._events: dict[str, threading.Event] = {}
        self._lock = threading.Lock()

    def request(self, task_id: str) -> None:
        with self._lock:
            event = self._events.get(task_id)
            if event is None:
                event = threading.Event()
                self._events[task_id] = event
            event.set()

    def clear(self, task_id: str) -> None:
        with self._lock:
            event = self._events.get(task_id)
            if event is not None:
                event.clear()

    def is_cancelled(self, task_id: str) -> bool:
        with self._lock:
            event = self._events.get(task_id)
        return event is not None and event.is_set()

    def pending_ids(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(task_id for task_id, event in self._events.items() if event.is_set())

    def remove(self, task_id: str) -> None:
        with self._lock:
            self._events.pop(task_id, None)


@lru_cache
def get_task_cancellation_registry() -> TaskCancellationRegistry:
    """获取进程级取消注册表。"""
    return TaskCancellationRegistry()
