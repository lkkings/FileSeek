"""Library 回收站的 Tortoise 仓储实现。"""

from fileseek.features.recycle.domain.entities import RecycleItem
from fileseek.features.recycle.domain.repositories import RecycleRepository
from fileseek.infrastructure.database.models import RecycleItemModel
from fileseek.shared.domain.file_types import FileType


def _to_entity(model: RecycleItemModel) -> RecycleItem:
    return RecycleItem(
        id=model.id,
        original_file_id=model.file.id,
        original_name=model.file.name,
        original_parent_folder=model.file.parent_folder_id,
        original_path=model.file.path,
        recycle_path=model.recycle_path,
        deleted_at=model.deleted_at.isoformat() if hasattr(model.deleted_at, "isoformat") else model.deleted_at,
        file_type=FileType(model.file.file_type),
        size=model.file.size
    )


class RecycleRepositoryImpl(RecycleRepository):
    async def get_by_id(self, item_id: str) -> RecycleItem | None:
        return await self._get_by_id(item_id)

    async def _get_by_id(self, item_id: str) -> RecycleItem | None:
        model = await RecycleItemModel.get_or_none(id=item_id).prefetch_related("file")
        return _to_entity(model) if model else None

    async def list_all(self, page: int, page_size: int) -> tuple[list[RecycleItem], int]:
        return await self._list_all(page, page_size)

    async def _list_all(self, page: int, page_size: int) -> tuple[list[RecycleItem], int]:
        query = RecycleItemModel.all().prefetch_related("file")
        total = await query.count()
        models = await query.order_by("-deleted_at").offset((page - 1) * page_size).limit(page_size)
        return [_to_entity(model) for model in models], total

    async def list_all_items(self) -> list[RecycleItem]:
        return await self._list_all_items()

    async def _list_all_items(self) -> list[RecycleItem]:
        return [_to_entity(model) for model in await RecycleItemModel.all().prefetch_related("file").order_by("-deleted_at")]

    async def save(self, item: RecycleItem) -> None:
        await self._save(item)

    async def _save(self, item: RecycleItem) -> None:
        await RecycleItemModel.update_or_create(
            id=item.id,
            defaults={
                "file_id": item.original_file_id,
                "recycle_path": item.recycle_path,
                "deleted_at": item.deleted_at,
            }
        )

    async def delete(self, item_id: str) -> None:
        await self._delete(item_id)

    async def _delete(self, item_id: str) -> None:
        await RecycleItemModel.filter(id=item_id).delete()

    async def delete_all(self) -> None:
        await self._delete_all()

    async def _delete_all(self) -> None:
        await RecycleItemModel.all().delete()

