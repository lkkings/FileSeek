from __future__ import annotations

from fileseek.features.library.application.commands import (
    AddFileCommand,
    CreateFolderCommand,
    AddFiles2RecycleCommand,
    DeleteFolderCommand,
    DeletePermanentlyCommand,
    RestoreItemCommand,
    UpdateFolderCommand,
)
from fileseek.features.library.application.dto import FileDTO, FolderDTO, RecycleItemDTO
from fileseek.features.library.application.queries import (
    GetFileQuery,
    ListFilesQuery,
    ListFoldersQuery,
    ListRecentAccessQuery,
    ListRecycleItemsQuery,
)
from fileseek.features.library.interfaces.http.schemas import (
    FileImportRequest,
    FileResponse,
    FolderCreateRequest,
    FolderResponse,
    FolderUpdateRequest,
    RecycleItemResponse,
)


def folder_to_schema(folder: FolderDTO) -> FolderResponse:
    return FolderResponse(
        id=folder.id,
        name=folder.name,
        iconType=folder.icon_type,
        description=folder.description,
        modified=folder.modified,
        file_count=folder.file_count,
    )


def file_to_schema(file: FileDTO) -> FileResponse:
    return FileResponse(
        id=file.id,
        name=file.name,
        FileType=file.file_type,
        size=str(file.size),
        modified=file.modified,
        parentFolder=file.parent_folder,
        path=file.path,
    )


def recycle_item_to_schema(item: RecycleItemDTO) -> RecycleItemResponse:
    return RecycleItemResponse(
        id=item.id,
        original_file_id=item.original_file_id,
        original_name=item.original_name,
        original_path=item.original_path,
        deleted_at=item.deleted_at,
        file_type=item.file_type,
        size=str(item.size),
    )


def create_folder_request_to_command(body: FolderCreateRequest) -> CreateFolderCommand:
    return CreateFolderCommand(body.name, body.iconType, body.description)


def update_folder_request_to_command(
    folder_id: str, body: FolderUpdateRequest
) -> UpdateFolderCommand:
    return UpdateFolderCommand(folder_id, body.name, body.iconType, body.description)


def list_folders_query() -> ListFoldersQuery:
    return ListFoldersQuery()


def list_files_query(
    folder: str | None, file_type: str | None, page: int, page_size: int
) -> ListFilesQuery:
    return ListFilesQuery(folder, file_type, page, page_size)


def list_recycle_query(page: int, page_size: int) -> ListRecycleItemsQuery:
    return ListRecycleItemsQuery(page, page_size)


def list_recent_query(limit: int) -> ListRecentAccessQuery:
    return ListRecentAccessQuery(limit)


def delete_folder_command(folder_id: str) -> DeleteFolderCommand:
    return DeleteFolderCommand(folder_id)


def delete_files_command(file_ids: list[str]) -> AddFiles2RecycleCommand:
    return AddFiles2RecycleCommand(file_ids)


def restore_item_command(item_id: str) -> RestoreItemCommand:
    return RestoreItemCommand(item_id)


def delete_permanently_command(item_id: str) -> DeletePermanentlyCommand:
    return DeletePermanentlyCommand(item_id)


def add_file_request_to_command(body: FileImportRequest) -> AddFileCommand:
    return AddFileCommand(body.folder_id, body.filename, body.path)


def get_file_query(file_id: str) -> GetFileQuery:
    return GetFileQuery(file_id)

