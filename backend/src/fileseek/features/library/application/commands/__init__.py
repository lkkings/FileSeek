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
    path: str

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
class MoveFilesCommand:
    file_ids: tuple[str, ...]
    target_folder_id: str
