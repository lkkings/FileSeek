"""Library 回收站的 Tortoise 仓储实现。"""

from fileseek.features.library.domain.entities import RecycleItem
from fileseek.features.library.domain.repositories import RecycleRepository
from fileseek.infrastructure.database.models import RecycleItemModel
from fileseek.shared.domain.file_types import FileType


def _to_entity(model: RecycleItemModel) -> RecycleItem:
    return RecycleItem(id=model.id, original_file_id=model.original_file_id,
                       original_name=model.original_name,
                       original_parent_folder=model.original_parent_folder,
                       original_path=model.original_path, recycle_path=model.recycle_path,
                       deleted_at=model.deleted_at,
                       file_type=FileType(model.file_type), size=model.size)


class RecycleRepositoryImpl(RecycleRepository):
    async def get_by_id(self, item_id: str) -> RecycleItem | None:
        return await self._get_by_id(item_id)

    async def _get_by_id(self, item_id: str) -> RecycleItem | None:
        model = await RecycleItemModel.get_or_none(id=item_id)
        return _to_entity(model) if model else None

    async def list_all(self, page: int, page_size: int) -> tuple[list[RecycleItem], int]:
        return await self._list_all(page, page_size)

    async def _list_all(self, page: int, page_size: int) -> tuple[list[RecycleItem], int]:
        query = RecycleItemModel.all()
        total = await query.count()
        models = await query.order_by("-deleted_at").offset((page - 1) * page_size).limit(page_size)
        return [_to_entity(model) for model in models], total

    async def list_all_items(self) -> list[RecycleItem]:
        return await self._list_all_items()

    async def _list_all_items(self) -> list[RecycleItem]:
        return [_to_entity(model) for model in await RecycleItemModel.all().order_by("-deleted_at")]

    async def save(self, item: RecycleItem) -> None:
        await self._save(item)

    async def _save(self, item: RecycleItem) -> None:
        await RecycleItemModel.create(id=item.id, original_file_id=item.original_file_id,
            original_name=item.original_name, original_parent_folder=item.original_parent_folder,
            original_path=item.original_path, recycle_path=item.recycle_path,
            deleted_at=item.deleted_at,
            file_type=item.file_type.value, size=item.size)

    async def delete(self, item_id: str) -> None:
        await self._delete(item_id)

    async def _delete(self, item_id: str) -> None:
        await RecycleItemModel.filter(id=item_id).delete()

    async def delete_all(self) -> None:
        await self._delete_all()

    async def _delete_all(self) -> None:
        await RecycleItemModel.all().delete()
