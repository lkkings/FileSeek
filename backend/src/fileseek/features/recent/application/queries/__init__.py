from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ListRecentAccessQuery:
    limit: int = 20
