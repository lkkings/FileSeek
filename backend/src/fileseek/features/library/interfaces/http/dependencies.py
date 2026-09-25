from __future__ import annotations

from fastapi import Request

from fileseek.features.library.application.use_cases import (
    AddFileUseCase,
    CreateFolderUseCase,
    DeleteFolderUseCase,
    GetFileUseCase,
    ListFilesUseCase,
    ListFoldersUseCase,
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

def get_get_file_use_case(request: Request) -> GetFileUseCase:
    return resolve_dependency(request, "get_file_use_case")
