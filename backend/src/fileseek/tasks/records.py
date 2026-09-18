"""Task records and the transitions a task may make.

Stages are recorded as a task progresses so a retry can resume rather than redo
expensive work like video frame extraction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

TaskStatus = Literal["queued", "processing", "completed", "failed"]

Stage = Literal["moved", "extracted", "encoded", "indexed"]

STAGE_ORDER: tuple[Stage, ...] = ("moved", "extracted", "encoded", "indexed")

# Interactive submissions jump ahead of a bulk import already in the queue.
PRIORITY_INTERACTIVE = 100
PRIORITY_BATCH = 0

TERMINAL_STATUSES: frozenset[TaskStatus] = frozenset({"completed"})

_ALLOWED_TRANSITIONS: dict[TaskStatus, frozenset[TaskStatus]] = {
    # processing -> queued covers both restart recovery and pausing on NAS loss.
    "queued": frozenset({"processing", "failed"}),
    "processing": frozenset({"completed", "failed", "queued"}),
    "failed": frozenset({"queued"}),
    "completed": frozenset(),
}


class IllegalTransitionError(ValueError):
    def __init__(self, current: TaskStatus, requested: TaskStatus) -> None:
        super().__init__(f"cannot move task from {current!r} to {requested!r}")
        self.current = current
        self.requested = requested


def can_transition(current: TaskStatus, requested: TaskStatus) -> bool:
    return requested in _ALLOWED_TRANSITIONS[current]


def ensure_transition(current: TaskStatus, requested: TaskStatus) -> None:
    if not can_transition(current, requested):
        raise IllegalTransitionError(current, requested)


@dataclass(frozen=True)
class TaskRecord:
    id: str
    source_path: str
    status: TaskStatus
    created_at: int
    media_type: str | None = None
    file_id: str | None = None
    stage: Stage | None = None
    progress: int = 0
    completed_stages: tuple[Stage, ...] = field(default_factory=tuple)
    error_message: str | None = None
    priority: int = PRIORITY_BATCH
    started_at: int | None = None
    completed_at: int | None = None

    @property
    def is_interactive(self) -> bool:
        return self.priority >= PRIORITY_INTERACTIVE

    def has_completed(self, stage: Stage) -> bool:
        return stage in self.completed_stages

    def next_stage(self) -> Stage | None:
        """The first stage still outstanding, which is where a retry resumes."""
        for stage in STAGE_ORDER:
            if stage not in self.completed_stages:
                return stage
        return None
