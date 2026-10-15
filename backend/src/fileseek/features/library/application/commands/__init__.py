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
    storage_id: str = "local"


@dataclass(frozen=True)
class BatchImportItemCommand:
    path: str
    storage_id: str = "local"


@dataclass(frozen=True)
class BatchImportCommand:
    folder_id: str
    items: tuple[BatchImportItemCommand, ...]


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


@dataclass(frozen=True)
class CreateFolderSourceBindingCommand:
    folder_id: str
    storage_id: str
    path: str
    recursive: bool = True
    enabled: bool = True


@dataclass(frozen=True)
class UpdateFolderSourceBindingCommand:
    binding_id: str
    folder_id: str
    storage_id: str
    path: str
    recursive: bool = True
    enabled: bool = True


@dataclass(frozen=True)
class DeleteFolderSourceBindingCommand:
    binding_id: str
