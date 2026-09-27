from __future__ import annotations

from fileseek.features.library.application.mappers import file_to_dto
from fileseek.features.library.domain.repositories import FileRepository
from fileseek.features.recent.application.dto import RecentAccessDTO
from fileseek.features.recent.application.queries import ListRecentAccessQuery
from fileseek.features.recent.domain.repositories import RecentAccessRepository


class ListRecentAccessUseCase:
    def __init__(
        self,
        recent_repo: RecentAccessRepository,
        file_repo: FileRepository,
    ) -> None:
        self.recent_repo = recent_repo
        self.file_repo = file_repo

    async def execute(
        self,
        query: ListRecentAccessQuery,
    ) -> tuple[list[RecentAccessDTO], int]:
        records, total = await self.recent_repo.list_recent_paginated(
            query.page,
            query.page_size,
        )

        dtos = []
        for record in records:
            file_entity = await self.file_repo.get_by_id(record.file_id)
            file_dto = file_to_dto(file_entity) if file_entity else None
            dtos.append(
                RecentAccessDTO(
                    id=record.id,
                    file_id=record.file_id,
                    accessed_at=record.accessed_at,
                    file=file_dto,
                )
            )

        return dtos, total
