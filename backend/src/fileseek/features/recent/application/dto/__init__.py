from __future__ import annotations

from dataclasses import dataclass

from fileseek.features.library.application.dto import FileDTO


@dataclass(frozen=True)
class RecentAccessDTO:
    id: int
    file_id: str
    accessed_at: str
    file: FileDTO | None = None
