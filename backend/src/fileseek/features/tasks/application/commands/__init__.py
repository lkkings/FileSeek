from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RetryTaskCommand:
    task_id: str


