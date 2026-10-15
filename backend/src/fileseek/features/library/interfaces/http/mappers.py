from __future__ import annotations

from fileseek.features.library.application.commands import (
    BatchImportCommand,
    BatchImportItemCommand,
    CreateFolderCommand,
    CreateFolderSourceBindingCommand,
    DeleteFolderCommand,
    DeleteFolderSourceBindingCommand,
    MoveFilesCommand,
    UpdateFolderCommand,
    UpdateFolderSourceBindingCommand,
)
from fileseek.features.library.application.dto import (
    FileAvailabilityDTO,
    FileDTO,
    FolderDTO,
    FolderSourceBindingDTO,
)
from fileseek.features.library.application.queries import (
    CheckFileAvailabilityQuery,
    GetFileQuery,
    GetFileThumbnailQuery,
    ListFoldersQuery,
)
from fileseek.features.library.interfaces.http.schemas import (
    BatchImportRequest,
    FileResponse,
    FolderCreateRequest,
    FolderResponse,
    FolderSourceBindingCreateRequest,
    FolderSourceBindingResponse,
    FolderSourceBindingUpdateRequest,
    FolderUpdateRequest,
    MoveFilesRequest,
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


def folder_source_binding_to_schema(
    binding: FolderSourceBindingDTO,
) -> FolderSourceBindingResponse:
    return FolderSourceBindingResponse(
        id=binding.id,
        folder_id=binding.folder_id,
        storage_id=binding.storage_id,
        source_path=binding.source_path,
        recursive=binding.recursive,
        enabled=binding.enabled,
        watch_status=binding.watch_status,
        last_error=binding.last_error,
        last_error_at=binding.last_error_at,
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


def update_folder_request_to_command(
    folder_id: str,
    body: FolderUpdateRequest,
) -> UpdateFolderCommand:
    return UpdateFolderCommand(folder_id, body.name, body.icon_type, body.description)


def create_folder_source_binding_request_to_command(
    folder_id: str,
    body: FolderSourceBindingCreateRequest,
) -> CreateFolderSourceBindingCommand:
    return CreateFolderSourceBindingCommand(
        folder_id=folder_id,
        storage_id=body.storage_id,
        path=body.path,
        recursive=body.recursive,
        enabled=body.enabled,
    )


def update_folder_source_binding_request_to_command(
    folder_id: str,
    binding_id: str,
    body: FolderSourceBindingUpdateRequest,
) -> UpdateFolderSourceBindingCommand:
    return UpdateFolderSourceBindingCommand(
        binding_id=binding_id,
        folder_id=folder_id,
        storage_id=body.storage_id,
        path=body.path,
        recursive=body.recursive,
        enabled=body.enabled,
    )


def delete_folder_source_binding_command(
    binding_id: str,
) -> DeleteFolderSourceBindingCommand:
    return DeleteFolderSourceBindingCommand(binding_id)


def list_folders_query() -> ListFoldersQuery:
    return ListFoldersQuery()


def delete_folder_command(folder_id: str) -> DeleteFolderCommand:
    return DeleteFolderCommand(folder_id)


def batch_import_request_to_command(body: BatchImportRequest) -> BatchImportCommand:
    return BatchImportCommand(
        folder_id=body.folder_id,
        items=tuple(
            BatchImportItemCommand(path=item.path, storage_id=item.storage_id)
            for item in body.items
        ),
    )


def move_files_request_to_command(body: MoveFilesRequest) -> MoveFilesCommand:
    return MoveFilesCommand(tuple(body.file_ids), body.target_folder_id)


def get_file_query(file_id: str) -> GetFileQuery:
    return GetFileQuery(file_id)


def get_file_thumbnail_query(file_id: str, size: str) -> GetFileThumbnailQuery:
    return GetFileThumbnailQuery(file_id=file_id, size=size)


def check_file_availability_query(file_id: str) -> CheckFileAvailabilityQuery:
    return CheckFileAvailabilityQuery(file_id=file_id)


def file_availability_to_schema(value: FileAvailabilityDTO) -> dict[str, str]:
    return {
        "id": value.id,
        "access_state": value.access_state,
        "last_checked_at": value.last_checked_at,
    }
