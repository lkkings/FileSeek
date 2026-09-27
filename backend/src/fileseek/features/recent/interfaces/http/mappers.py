from __future__ import annotations

from fileseek.features.library.interfaces.http.mappers import file_to_schema
from fileseek.features.recent.application.commands import RecordAccessCommand
from fileseek.features.recent.application.dto import RecentAccessDTO
from fileseek.features.recent.application.queries import ListRecentAccessQuery
from fileseek.features.recent.interfaces.http.schemas.recent import (
    RecentAccessPageResponse,
    RecentAccessResponse,
)


def list_recent_query(page: int, page_size: int) -> ListRecentAccessQuery:
    return ListRecentAccessQuery(page, page_size)


def record_access_command(file_id: str) -> RecordAccessCommand:
    return RecordAccessCommand(file_id)


def recent_access_to_schema(dto: RecentAccessDTO) -> RecentAccessResponse:
    return RecentAccessResponse(
        id=dto.id,
        file_id=dto.file_id,
        accessed_at=dto.accessed_at.isoformat()
        if hasattr(dto.accessed_at, "isoformat")
        else dto.accessed_at,
        file=file_to_schema(dto.file) if dto.file else None,
    )


def recent_access_page_to_response(
    dtos: list[RecentAccessDTO],
    total: int,
    page: int,
    page_size: int,
) -> RecentAccessPageResponse:
    offset = (page - 1) * page_size
    has_more = offset + page_size < total
    return RecentAccessPageResponse(
        items=[recent_access_to_schema(dto) for dto in dtos],
        page_number=page,
        page_size=page_size,
        total=total,
        has_more=has_more,
    )
