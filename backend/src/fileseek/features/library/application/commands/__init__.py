from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CreateFolderCommand:
    name: str
    icon_type: str
    description: str

@dataclass(frozen=True)
class AddFileCommand:
    folder_id: str
    filename: str
    path: str

@dataclass(frozen=True)
class DeleteFileCommand:
    file_id: str


@dataclass(frozen=True)
class UpdateFolderCommand:
    folder_id: str
    name: str
    icon_type: str
    description: str


@dataclass(frozen=True)
class DeleteFolderCommand:
    folder_id: str


@dataclass(frozen=True)
class AddFiles2RecycleCommand:
    file_ids: list[str]


@dataclass(frozen=True)
class RestoreItemCommand:
    item_id: str


@dataclass(frozen=True)
class DeletePermanentlyCommand:
    item_id: str


@dataclass(frozen=True)
class ClearRecycleBinCommand:
    pass


@dataclass(frozen=True)
class RecordAccessCommand:
    file_id: str
