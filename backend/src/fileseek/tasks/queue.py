"""The ingest queue, backed by the tasks table.

A desktop app should not need an external broker, so the table *is* the queue:
claims happen in a transaction, progress is durable, and a restart recovers
in-flight work instead of losing it.
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from collections.abc import Sequence

from fileseek.tasks.records import (
    PRIORITY_BATCH,
    PRIORITY_INTERACTIVE,
    Stage,
    TaskRecord,
    TaskStatus,
    ensure_transition,
)

DEFAULT_MAX_CONCURRENT = 3

_SELECT_TASK = """
SELECT id, source_path, media_type, file_id, status, stage, progress,
       completed_stages, error_message, priority, created_at, started_at, completed_at
FROM tasks
"""

_INSERT_TASK = """
INSERT INTO tasks (id, source_path, media_type, status, progress, completed_stages,
                   priority, created_at)
VALUES (?, ?, ?, 'queued', 0, '[]', ?, ?)
"""

# Highest priority first, oldest first within a priority.
_NEXT_CLAIMABLE = f"""
{_SELECT_TASK}
WHERE status = 'queued'
ORDER BY priority DESC, created_at ASC, id ASC
LIMIT 1
"""


class TaskNotFoundError(LookupError):
    def __init__(self, task_id: str) -> None:
        super().__init__(f"no such task: {task_id}")
        self.task_id = task_id


class ProgressRegressionError(ValueError):
    """Progress may only move forward, so the UI never appears to rewind."""

    def __init__(self, task_id: str, current: int, requested: int) -> None:
        super().__init__(
            f"progress for task {task_id} may not go backwards: {current} -> {requested}"
        )
        self.task_id = task_id
        self.current = current
        self.requested = requested


def _now() -> int:
    return int(time.time())


def _to_task(row: sqlite3.Row) -> TaskRecord:
    return TaskRecord(
        id=row["id"],
        source_path=row["source_path"],
        media_type=row["media_type"],
        file_id=row["file_id"],
        status=row["status"],
        stage=row["stage"],
        progress=row["progress"],
        completed_stages=tuple(json.loads(row["completed_stages"])),
        error_message=row["error_message"],
        priority=row["priority"],
        created_at=row["created_at"],
        started_at=row["started_at"],
        completed_at=row["completed_at"],
    )


class TaskQueue:
    def __init__(
        self,
        connection: sqlite3.Connection,
        max_concurrent: int = DEFAULT_MAX_CONCURRENT,
    ) -> None:
        if max_concurrent < 1:
            raise ValueError("max_concurrent must be at least 1")
        self._connection = connection
        self._max_concurrent = max_concurrent

    @property
    def max_concurrent(self) -> int:
        return self._max_concurrent

    def enqueue(
        self,
        source_path: str,
        media_type: str | None = None,
        interactive: bool = False,
        created_at: int | None = None,
    ) -> TaskRecord:
        task_id = str(uuid.uuid4())
        priority = PRIORITY_INTERACTIVE if interactive else PRIORITY_BATCH
        timestamp = created_at if created_at is not None else _now()
        self._connection.execute(
            _INSERT_TASK, (task_id, source_path, media_type, priority, timestamp)
        )
        return self.get(task_id)

    def enqueue_many(
        self, source_paths: Sequence[str], interactive: bool = False
    ) -> list[TaskRecord]:
        return [self.enqueue(path, interactive=interactive) for path in source_paths]

    def get(self, task_id: str) -> TaskRecord:
        row = self._connection.execute(f"{_SELECT_TASK} WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            raise TaskNotFoundError(task_id)
        return _to_task(row)

    def find(self, task_id: str) -> TaskRecord | None:
        row = self._connection.execute(f"{_SELECT_TASK} WHERE id = ?", (task_id,)).fetchone()
        return None if row is None else _to_task(row)

    def list_by_status(self, status: TaskStatus) -> list[TaskRecord]:
        rows = self._connection.execute(
            f"{_SELECT_TASK} WHERE status = ? ORDER BY priority DESC, created_at ASC, id ASC",
            (status,),
        ).fetchall()
        return [_to_task(row) for row in rows]

    def active_count(self) -> int:
        row = self._connection.execute(
            "SELECT count(*) AS n FROM tasks WHERE status = 'processing'"
        ).fetchone()
        return int(row["n"])

    def has_capacity(self) -> bool:
        return self.active_count() < self._max_concurrent

    def claim_next(self) -> TaskRecord | None:
        """Atomically take the next queued task, or None if none is available.

        The IMMEDIATE transaction plus the status guard on UPDATE means two
        concurrent workers can never claim the same row.
        """
        if not self.has_capacity():
            return None

        self._connection.execute("BEGIN IMMEDIATE")
        try:
            row = self._connection.execute(_NEXT_CLAIMABLE).fetchone()
            if row is None:
                self._connection.execute("COMMIT")
                return None

            claimed = self._connection.execute(
                "UPDATE tasks SET status = 'processing', started_at = ? "
                "WHERE id = ? AND status = 'queued'",
                (_now(), row["id"]),
            )
            if claimed.rowcount == 0:
                self._connection.execute("COMMIT")
                return None
            self._connection.execute("COMMIT")
        except BaseException:
            self._connection.execute("ROLLBACK")
            raise

        return self.get(row["id"])

    def report_progress(
        self, task_id: str, progress: int, stage: Stage | None = None
    ) -> TaskRecord:
        if not 0 <= progress <= 100:
            raise ValueError(f"progress must be between 0 and 100, got {progress}")
        current = self.get(task_id)
        if progress < current.progress:
            raise ProgressRegressionError(task_id, current.progress, progress)

        self._connection.execute(
            "UPDATE tasks SET progress = ?, stage = coalesce(?, stage) WHERE id = ?",
            (progress, stage, task_id),
        )
        return self.get(task_id)

    def complete_stage(self, task_id: str, stage: Stage) -> TaskRecord:
        """Record a finished stage so a retry can skip it."""
        current = self.get(task_id)
        if stage in current.completed_stages:
            return current
        stages = [*current.completed_stages, stage]
        self._connection.execute(
            "UPDATE tasks SET completed_stages = ?, stage = ? WHERE id = ?",
            (json.dumps(stages), stage, task_id),
        )
        return self.get(task_id)

    def mark_completed(self, task_id: str, file_id: str | None = None) -> TaskRecord:
        current = self.get(task_id)
        ensure_transition(current.status, "completed")
        self._connection.execute(
            "UPDATE tasks SET status = 'completed', progress = 100, completed_at = ?, "
            "file_id = coalesce(?, file_id), error_message = NULL WHERE id = ?",
            (_now(), file_id, task_id),
        )
        return self.get(task_id)

    def mark_failed(self, task_id: str, error_message: str) -> TaskRecord:
        current = self.get(task_id)
        ensure_transition(current.status, "failed")
        self._connection.execute(
            "UPDATE tasks SET status = 'failed', error_message = ?, completed_at = ? WHERE id = ?",
            (error_message, _now(), task_id),
        )
        return self.get(task_id)

    def retry(self, task_id: str) -> TaskRecord:
        """Requeue a failed task, keeping its completed stages so work is reused."""
        current = self.get(task_id)
        ensure_transition(current.status, "queued")
        self._connection.execute(
            "UPDATE tasks SET status = 'queued', error_message = NULL, started_at = NULL, "
            "completed_at = NULL WHERE id = ?",
            (task_id,),
        )
        return self.get(task_id)

    def release(self, task_id: str) -> TaskRecord:
        """Put an in-flight task back in the queue, e.g. when the NAS drops."""
        current = self.get(task_id)
        ensure_transition(current.status, "queued")
        self._connection.execute(
            "UPDATE tasks SET status = 'queued', started_at = NULL WHERE id = ?", (task_id,)
        )
        return self.get(task_id)

    def recover_interrupted(self) -> int:
        """Requeue tasks left mid-flight by a crash; completed stages survive."""
        cursor = self._connection.execute(
            "UPDATE tasks SET status = 'queued', started_at = NULL WHERE status = 'processing'"
        )
        return cursor.rowcount

    def purge_completed(self, older_than: int) -> int:
        cursor = self._connection.execute(
            "DELETE FROM tasks WHERE status = 'completed' AND completed_at < ?", (older_than,)
        )
        return cursor.rowcount
