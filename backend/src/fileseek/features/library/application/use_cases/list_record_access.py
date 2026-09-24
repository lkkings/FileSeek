from fileseek.features.library.domain.entities import RecentAccessRecord
from fileseek.features.library.domain.repositories import RecentAccessRepository
from fileseek.features.library.application.queries import ListRecentAccessQuery
from fileseek.features.library.application.dto import RecentAccessDTO
from fileseek.features.library.application.mappers import recent_access_to_dto


class ListRecentAccessUseCase:
    def __init__(self, recent_repo: RecentAccessRepository) -> None:
        self.recent_repo = recent_repo

    async def execute(self, query: ListRecentAccessQuery) -> list[RecentAccessDTO]:
        return [recent_access_to_dto(item) for item in await self.recent_repo.list_recent(query.limit)]
