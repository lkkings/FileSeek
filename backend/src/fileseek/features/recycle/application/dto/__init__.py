from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RecycleItemDTO:
    id: str
    original_file_id: str
    original_name: str
    original_path: str
    deleted_at: str
    file_type: str
    size: int
