"""Library 文件夹的 Tortoise 仓储实现。"""

from tortoise.functions import Count

from fileseek.features.library.domain.entities import Folder
from fileseek.features.library.domain.repositories import FolderRepository
from fileseek.infrastructure.database.models import FileModel, FolderModel


def _to_entity(model: FolderModel, file_count: int) -> Folder:
    return Folder(
        id=model.id,
        name=model.name,
        icon_type=model.icon_type,
        description=model.description,
        modified=model.modified,
        file_count=file_count,
    )


class FolderRepositoryImpl(FolderRepository):
    async def get_by_id(self, folder_id: str) -> Folder | None:
        return await self._get_by_id(folder_id)

    async def _get_by_id(self, folder_id: str) -> Folder | None:
        model = await FolderModel.get_or_none(id=folder_id)
        if model is None:
            return None
        file_count = await self._count_files(folder_id)
        return _to_entity(model, file_count)

    async def get_by_name(self, name: str) -> Folder | None:
        return await self._get_by_name(name)

    async def _get_by_name(self, name: str) -> Folder | None:
        model = await FolderModel.get_or_none(name=name)
        if model is None:
            return None
        file_count = await self._count_files(model.id)
        return _to_entity(model, file_count)

    async def list_all(self) -> list[Folder]:
        return await self._list_all()

    async def _list_all(self) -> list[Folder]:
        models = await FolderModel.all().order_by("-modified")
        file_counts = await self._count_files_batch([model.id for model in models])
        return [
            _to_entity(model, file_counts.get(model.id, 0))
            for model in models
        ]

    async def save(self, folder: Folder) -> None:
        await self._save(folder)

    async def _save(self, folder: Folder) -> None:
        await FolderModel.update_or_create(
            id=folder.id,
            defaults={
                "name": folder.name,
                "icon_type": folder.icon_type,
                "description": folder.description,
                "modified": folder.modified,
            },
        )

    async def delete(self, folder_id: str) -> None:
        await self._delete(folder_id)

    async def _delete(self, folder_id: str) -> None:
        await FolderModel.filter(id=folder_id).delete()

    async def _count_files(self, folder_id: str) -> int:
        return int(
            await FileModel.filter(
                folder_id=folder_id,
                recycle_item__isnull=True,
            ).count()
        )

    async def _count_files_batch(
        self,
        folder_ids: list[str],
    ) -> dict[str, int]:
        if not folder_ids:
            return {}

        rows = await (
            FileModel.filter(
                folder_id__in=folder_ids,
                recycle_item__isnull=True,
            )
            .group_by("folder_id")
            .annotate(count=Count("id"))
            .values("folder_id", "count")
        )
        return {row["folder_id"]: int(row["count"]) for row in rows}
