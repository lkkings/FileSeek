from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RecentAccessDTO:
    file_id: str
    accessed_at: str
