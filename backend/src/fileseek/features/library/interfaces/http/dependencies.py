from __future__ import annotations

from fastapi import Request

from fileseek.features.library.application.use_cases import (
    BatchImportSessionManager,
    CheckFileAvailabilityUseCase,
    CreateFolderUseCase,
    DeleteFolderUseCase,
    GetFileThumbnailUseCase,
    GetFileUseCase,
    GetFileSourceUseCase,
    ListFoldersUseCase,
    ListTagsUseCase,
    MoveFilesUseCase,
    StartBatchImportUseCase,
    UpdateFolderUseCase,
)
from fileseek.shared.application.dependencies import resolve_dependency


def get_list_folders_use_case(request: Request) -> ListFoldersUseCase:
    return resolve_dependency(request, "list_folders_use_case")


def get_list_tags_use_case(request: Request) -> ListTagsUseCase:
    return resolve_dependency(request, "list_tags_use_case")

def get_create_folder_use_case(request: Request) -> CreateFolderUseCase:
    return resolve_dependency(request, "create_folder_use_case")

def get_update_folder_use_case(request: Request) -> UpdateFolderUseCase:
    return resolve_dependency(request, "update_folder_use_case")

def get_delete_folder_use_case(request: Request) -> DeleteFolderUseCase:
    return resolve_dependency(request, "delete_folder_use_case")


def get_start_batch_import_use_case(
    request: Request,
) -> StartBatchImportUseCase:
    return resolve_dependency(request, "start_batch_import_use_case")


def get_batch_import_session_manager(
    request: Request,
) -> BatchImportSessionManager:
    return resolve_dependency(request, "batch_import_session_manager")

def get_get_file_use_case(request: Request) -> GetFileUseCase:
    return resolve_dependency(request, "get_file_use_case")


def get_get_file_source_use_case(request: Request) -> GetFileSourceUseCase:
    return resolve_dependency(request, "get_file_source_use_case")


def get_file_thumbnail_use_case(request: Request) -> GetFileThumbnailUseCase:
    return resolve_dependency(request, "get_file_thumbnail_use_case")


def get_move_files_use_case(request: Request) -> MoveFilesUseCase:
    return resolve_dependency(request, "move_files_use_case")


def get_check_file_availability_use_case(
    request: Request,
) -> CheckFileAvailabilityUseCase:
    return resolve_dependency(request, "check_file_availability_use_case")
