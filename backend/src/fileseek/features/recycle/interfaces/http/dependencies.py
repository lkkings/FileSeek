from __future__ import annotations

from fastapi import Request

from fileseek.features.recycle.application.use_cases import (
    AddFiles2RecycleUseCase,
    ClearRecycleBinUseCase,
    DeleteRecycleUseCase,
    ListRecycleItemsUseCase,
    RestoreRecycleUseCase,
)
from fileseek.shared.application.dependencies import resolve_dependency


def get_add_files2recycle_use_case(request: Request) -> AddFiles2RecycleUseCase:
    return resolve_dependency(request, "add_files2recycle_use_case")


def get_clear_recycle_bin_use_case(request: Request) -> ClearRecycleBinUseCase:
    return resolve_dependency(request, "clear_recycle_bin_use_case")


def get_delete_recycle_use_case(request: Request) -> DeleteRecycleUseCase:
    return resolve_dependency(request, "delete_recycle_use_case")


def get_list_recycle_items_use_case(request: Request) -> ListRecycleItemsUseCase:
    return resolve_dependency(request, "list_recycle_items_use_case")


def get_restore_recycle_use_case(request: Request) -> RestoreRecycleUseCase:
    return resolve_dependency(request, "restore_recycle_use_case")
