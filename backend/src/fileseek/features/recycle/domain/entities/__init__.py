from __future__ import annotations

from dataclasses import dataclass

from fileseek.shared.domain.file_types import FileType


@dataclass
class RecycleItem:
    """回收站条目领域实体。"""

    id: str
    original_file_id: str
    original_name: str
    original_path: str
    deleted_at: str
    file_type: FileType
    size: int
    original_folder_id: str | None = None
    storage_id: str | None = None
    recycle_path: str | None = None


__all__ = ["RecycleItem"]
