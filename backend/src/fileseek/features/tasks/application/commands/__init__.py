from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RetryTaskCommand:
    task_id: str


@dataclass(frozen=True)
class CancelTaskCommand:
    task_id: str


@dataclass(frozen=True)
class DeleteTaskCommand:
    task_id: str
