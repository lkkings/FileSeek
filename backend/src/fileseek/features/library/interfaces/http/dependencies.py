from __future__ import annotations

from fastapi import Request

from fileseek.features.library.application.use_cases import (
    AddFileUseCase,
    ClearRecycleBinUseCase,
    CreateFolderUseCase,
    AddFiles2RecycleUseCase,
    DeleteFolderUseCase,
    DeleteRecycleUseCase,
    ListFilesUseCase,
    ListFoldersUseCase,
    ListRecentAccessUseCase,
    GetFileUseCase,
    ListRecycleItemsUseCase,
    RecordAccessUseCase,
    RestoreRecycleUseCase,
    UpdateFolderUseCase,
)
from fileseek.shared.application.dependencies import resolve_dependency


def get_list_folders_use_case(request: Request) -> ListFoldersUseCase:
    return resolve_dependency(request, "list_folders_use_case")


def get_create_folder_use_case(request: Request) -> CreateFolderUseCase:
    return resolve_dependency(request, "create_folder_use_case")


def get_update_folder_use_case(request: Request) -> UpdateFolderUseCase:
    return resolve_dependency(request, "update_folder_use_case")


def get_delete_folder_use_case(request: Request) -> DeleteFolderUseCase:
    return resolve_dependency(request, "delete_folder_use_case")


def get_list_files_use_case(request: Request) -> ListFilesUseCase:
    return resolve_dependency(request, "list_files_use_case")


def get_add_file_use_case(request: Request) -> AddFileUseCase:
    return resolve_dependency(request, "add_file_use_case")


def get_add_files2recycle_use_case(request: Request) -> AddFiles2RecycleUseCase:
    return resolve_dependency(request, "add_files2recycle_use_case")


def get_list_recycle_items_use_case(request: Request) -> ListRecycleItemsUseCase:
    return resolve_dependency(request, "list_recycle_items_use_case")


def get_restore_recycle_use_case(request: Request) -> RestoreRecycleUseCase:
    return resolve_dependency(request, "restore_recycle_use_case")


def get_delete_recycle_use_case(request: Request) -> DeleteRecycleUseCase:
    return resolve_dependency(request, "delete_recycle_use_case")


def get_clear_recycle_bin_use_case(request: Request) -> ClearRecycleBinUseCase:
    return resolve_dependency(request, "clear_recycle_bin_use_case")


def get_list_recent_access_use_case(request: Request) -> ListRecentAccessUseCase:
    return resolve_dependency(request, "list_recent_access_use_case")


def get_record_access_use_case(request: Request) -> RecordAccessUseCase:
    return resolve_dependency(request, "record_access_use_case")


def get_get_file_use_case(request: Request) -> GetFileUseCase:
    return resolve_dependency(request, "get_file_use_case")

