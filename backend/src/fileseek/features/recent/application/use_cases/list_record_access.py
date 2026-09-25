from fileseek.features.recent.application.dto import RecentAccessDTO
from fileseek.features.recent.application.mappers import recent_access_to_dto
from fileseek.features.recent.application.queries import ListRecentAccessQuery
from fileseek.features.recent.domain.repositories import RecentAccessRepository


class ListRecentAccessUseCase:
    def __init__(self, recent_repo: RecentAccessRepository) -> None:
        self.recent_repo = recent_repo

    async def execute(self, query: ListRecentAccessQuery) -> list[RecentAccessDTO]:
        return [recent_access_to_dto(item) for item in await self.recent_repo.list_recent(query.limit)]
