from __future__ import annotations

from fileseek.features.library.application.commands import (
    AddFileCommand,
    CreateFolderCommand,
    DeleteFolderCommand,
    UpdateFolderCommand,
)
from fileseek.features.library.application.dto import (
    FileDTO, 
    FolderDTO
)
from fileseek.features.library.application.queries import (
    GetFileQuery,
    ListFoldersQuery,
)
from fileseek.features.library.interfaces.http.schemas import (
    FileImportRequest,
    FileResponse,
    FolderCreateRequest,
    FolderResponse,
    FolderUpdateRequest,
)


def folder_to_schema(folder: FolderDTO) -> FolderResponse:
    return FolderResponse(
        id=folder.id,
        name=folder.name,
        icon_type=folder.icon_type,
        description=folder.description,
        modified=folder.modified,
        file_count=folder.file_count,
    )

def file_to_schema(file: FileDTO) -> FileResponse:
    return FileResponse(
        id=file.id,
        name=file.name,
        file_type=file.file_type,
        category=file.category,
        size=str(file.size),
        modified=file.modified,
        folder_id=file.folder_id,
        path=file.path,
    )

def create_folder_request_to_command(body: FolderCreateRequest) -> CreateFolderCommand:
    return CreateFolderCommand(body.name, body.icon_type, body.description)

def update_folder_request_to_command(folder_id: str, body: FolderUpdateRequest) -> UpdateFolderCommand:
    return UpdateFolderCommand(folder_id, body.name, body.icon_type, body.description)

def list_folders_query() -> ListFoldersQuery:
    return ListFoldersQuery()

def delete_folder_command(folder_id: str) -> DeleteFolderCommand:
    return DeleteFolderCommand(folder_id)

def add_file_request_to_command(body: FileImportRequest) -> AddFileCommand:
    return AddFileCommand(body.folder_id, body.path)

def get_file_query(file_id: str) -> GetFileQuery:
    return GetFileQuery(file_id)
