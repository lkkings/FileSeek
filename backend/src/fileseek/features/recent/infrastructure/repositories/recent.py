"""Library 最近访问记录的 Tortoise 仓储实现。"""

from typing import cast

from fileseek.features.recent.domain.entities import RecentAccessRecord
from fileseek.features.recent.domain.repositories import RecentAccessRepository
from fileseek.infrastructure.database.models import FileModel, RecentAccessModel


async def _active_file_ids() -> list[str]:
    return cast(
        "list[str]",
        await FileModel.filter(
            recycle_item__isnull=True,
        ).values_list("id", flat=True),
    )


def _to_record(model: RecentAccessModel) -> RecentAccessRecord:
    return RecentAccessRecord(
        id=model.id,
        file_id=model.file_id,
        accessed_at=model.accessed_at.isoformat(),
    )


class RecentAccessRepositoryImpl(RecentAccessRepository):
    async def record_access(self, file_id: str, accessed_at: str) -> None:
        await self._record_access(file_id, accessed_at)

    async def _record_access(self, file_id: str, accessed_at: str) -> None:
        await RecentAccessModel.update_or_create(
            defaults={"accessed_at": accessed_at},
            file_id=file_id,
        )

    async def list_recent(self, limit: int) -> list[RecentAccessRecord]:
        return await self._list_recent(limit)

    async def _list_recent(self, limit: int) -> list[RecentAccessRecord]:
        models = (
            await RecentAccessModel.filter(
                file_id__in=await _active_file_ids(),
            )
            .order_by("-accessed_at")
            .limit(limit)
        )
        return [_to_record(model) for model in models]

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
        query = RecentAccessModel.filter(
            file_id__in=await _active_file_ids(),
        )
        total = await query.count()
        models = (
            await query.order_by("-accessed_at")
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return [_to_record(model) for model in models], total

    async def delete(self, record_id: int) -> None:
        await self._delete(record_id)

    async def _delete(self, record_id: int) -> None:
        await RecentAccessModel.filter(id=record_id).delete()
