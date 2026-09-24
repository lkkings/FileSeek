"""Library 文件夹的 Tortoise 仓储实现。"""

from fileseek.features.library.domain.entities import Folder
from fileseek.features.library.domain.repositories import FolderRepository
from fileseek.infrastructure.database.models import FolderModel


def _to_entity(model: FolderModel) -> Folder:
    return Folder(id=model.id, name=model.name, icon_type=model.icon_type,
                  description=model.description, modified=model.modified,
                  file_count=model.file_count)


class FolderRepositoryImpl(FolderRepository):
    async def get_by_id(self, folder_id: str) -> Folder | None:
        return await self._get_by_id(folder_id)

    async def _get_by_id(self, folder_id: str) -> Folder | None:
        model = await FolderModel.get_or_none(id=folder_id)
        return _to_entity(model) if model else None

    async def get_by_name(self, name: str) -> Folder | None:
        return await self._get_by_name(name)

    async def _get_by_name(self, name: str) -> Folder | None:
        model = await FolderModel.get_or_none(name=name)
        return _to_entity(model) if model else None

    async def list_all(self) -> list[Folder]:
        return await self._list_all()

    async def _list_all(self) -> list[Folder]:
        return [_to_entity(model) for model in await FolderModel.all().order_by("-modified")]

    async def save(self, folder: Folder) -> None:
        await self._save(folder)

    async def _save(self, folder: Folder) -> None:
        await FolderModel.update_or_create(id=folder.id, defaults={
            "name": folder.name, "icon_type": folder.icon_type, "description": folder.description,
            "modified": folder.modified, "file_count": folder.file_count,
        })

    async def delete(self, folder_id: str) -> None:
        await self._delete(folder_id)

    async def _delete(self, folder_id: str) -> None:
        await FolderModel.filter(id=folder_id).delete()

    async def increment_file_count(self, folder_id: str, delta: int) -> None:
        await self._increment_file_count(folder_id, delta)

    async def _increment_file_count(self, folder_id: str, delta: int) -> None:
        model = await FolderModel.get_or_none(id=folder_id)
        if model:
            model.file_count += delta
            await model.save(update_fields=["file_count"])
