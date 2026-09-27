from __future__ import annotations

from fileseek.features.recent.domain.repositories import RecentAccessRepository


class DeleteRecentAccessUseCase:
    def __init__(self, recent_repo: RecentAccessRepository) -> None:
        self.recent_repo = recent_repo

    async def execute(self, record_id: int) -> None:
        await self.recent_repo.delete(record_id)
