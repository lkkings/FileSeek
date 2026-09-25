from fileseek.features.recycle.application.dto import RecycleItemDTO
from fileseek.features.recycle.application.mappers import recycle_item_to_dto
from fileseek.features.recycle.application.queries import ListRecycleItemsQuery
from fileseek.features.recycle.domain.repositories import RecycleRepository


class ListRecycleItemsUseCase:
    def __init__(self, recycle_repo: RecycleRepository) -> None:
        self.recycle_repo = recycle_repo

    async def execute(
        self,
        query: ListRecycleItemsQuery,
    ) -> tuple[list[RecycleItemDTO], int]:
        items, total = await self.recycle_repo.list_all(query.page, query.page_size)
        return [recycle_item_to_dto(item) for item in items], total
