from fileseek.features.library.domain.entities import RecycleItem
from fileseek.features.library.domain.repositories import RecycleRepository
from fileseek.features.library.application.queries import ListRecycleItemsQuery
from fileseek.features.library.application.dto import RecycleItemDTO
from fileseek.features.library.application.mappers import recycle_item_to_dto


class ListRecycleItemsUseCase:
    def __init__(self, recycle_repo: RecycleRepository) -> None:
        self.recycle_repo = recycle_repo

    async def execute(
        self,
        query: ListRecycleItemsQuery,
    ) -> tuple[list[RecycleItemDTO], int]:
        items, total = await self.recycle_repo.list_all(query.page, query.page_size)
        return [recycle_item_to_dto(item) for item in items], total
