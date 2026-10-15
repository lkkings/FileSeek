from __future__ import annotations

from fastapi import Request

from fileseek.features.recent.application.use_cases import (
    DeleteRecentAccessUseCase,
    ListRecentAccessUseCase,
    RecordAccessUseCase,
)
from fileseek.shared.application.dependencies import resolve_dependency


def get_list_recent_access_use_case(request: Request) -> ListRecentAccessUseCase:
    return resolve_dependency(request, "list_recent_access_use_case")


def get_record_access_use_case(request: Request) -> RecordAccessUseCase:
    return resolve_dependency(request, "record_access_use_case")


def get_delete_recent_access_use_case(request: Request) -> DeleteRecentAccessUseCase:
    return resolve_dependency(request, "delete_recent_access_use_case")
