"""Library 最近访问记录的 Tortoise 仓储实现。"""

from fileseek.features.recent.domain.entities import RecentAccessRecord
from fileseek.features.recent.domain.repositories import RecentAccessRepository
from fileseek.infrastructure.database.models import RecentAccessModel


class RecentAccessRepositoryImpl(RecentAccessRepository):
    async def record_access(self, file_id: str, accessed_at: str) -> None:
        await self._record_access(file_id, accessed_at)

    async def _record_access(self, file_id: str, accessed_at: str) -> None:
        await RecentAccessModel.create(file_id=file_id, accessed_at=accessed_at)

    async def list_recent(self, limit: int) -> list[RecentAccessRecord]:
        return await self._list_recent(limit)

    async def _list_recent(self, limit: int) -> list[RecentAccessRecord]:
        models = await RecentAccessModel.all().order_by("-accessed_at").limit(limit)
        return [RecentAccessRecord(id=model.id, file_id=model.file_id,
                                   accessed_at=model.accessed_at) for model in models]

    async def list_recent_paginated(
        self,
        page: int,
        page_size: int,
    ) -> tuple[list[RecentAccessRecord], int]:
        return await self._list_recent_paginated(page, page_size)

    async def _list_recent_paginated(
        self,
        page: int,
        page_size: int,
    ) -> tuple[list[RecentAccessRecord], int]:
        query = RecentAccessModel.all()
        total = await query.count()
        models = (
            await query.order_by("-accessed_at")
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        records = [
            RecentAccessRecord(
                id=model.id,
                file_id=model.file_id,
                accessed_at=model.accessed_at,
            )
            for model in models
        ]
        return records, total

    async def delete(self, record_id: int) -> None:
        await self._delete(record_id)

    async def _delete(self, record_id: int) -> None:
        await RecentAccessModel.filter(id=record_id).delete()
