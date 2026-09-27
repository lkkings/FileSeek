from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AddFiles2RecycleCommand:
    file_ids: list[str]

@dataclass(frozen=True)
class RestoreItemsCommand:
    item_ids: list[str]

@dataclass(frozen=True)
class DeletePermanentlyCommand:
    item_ids: list[str]

@dataclass(frozen=True)
class ClearRecycleBinCommand:
    pass
