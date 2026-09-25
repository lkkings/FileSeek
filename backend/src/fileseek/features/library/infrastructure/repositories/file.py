"""Library 文件的 Tortoise 仓储实现。"""
from datetime import datetime

from fileseek.features.library.domain.entities import File
from fileseek.features.library.domain.repositories import FileRepository
from fileseek.infrastructure.database.models import FileModel
from fileseek.shared.domain.file_types import FileType


def _as_iso(value: datetime | str) -> str:
    """把时间统一成 ISO 串。

    `FileModel.modified` 是 `DatetimeField`，读出来是 `datetime`；而 `File.modified`、
    `FileDTO.modified`、`FileResponse.modified` 三层都是 `str`（响应契约里这个字段就是字符串）。
    写入侧存的是 ISO 串，SQLite 收得下，于是"写进去是串、读出来是 datetime"，一直到 Pydantic
    校验才炸。类型在这一层收口，四条读路径就都对了。
    """
    return value.isoformat() if isinstance(value, datetime) else value


def _to_entity(model: FileModel) -> File:
    return File(
        id=model.id, name=model.name, file_type=FileType(model.file_type), size=model.size,
        modified=_as_iso(model.modified), parent_folder=model.parent_folder_id, path=model.path,
        tags=list(model.tags or []),
    )


class FileRepositoryImpl(FileRepository):
    async def get_by_id(self, file_id: str) -> File | None:
        return await self._get_by_id(file_id)

    async def _get_by_id(self, file_id: str) -> File | None:
        model = await FileModel.get_or_none(id=file_id)
        return _to_entity(model) if model else None

    async def list_by_folder(self, folder_id: str | None, file_type: str | None, page: int,
                       page_size: int) -> tuple[list[File], int]:
        return await self._list_by_folder(folder_id, file_type, page, page_size)

    async def _list_by_folder(self, folder_id: str | None, file_type: str | None, page: int,
                              page_size: int) -> tuple[list[File], int]:
        query = FileModel.filter(recycle_item__isnull=True)
        if folder_id is not None:
            query = query.filter(parent_folder_id=folder_id)
        if file_type is not None:
            query = query.filter(file_type=file_type)
        total = await query.count()
        models = await query.order_by("-modified").offset((page - 1) * page_size).limit(page_size)
        return [_to_entity(model) for model in models], total

    async def save(self, file: File) -> None:
        await self._save(file)

    async def _save(self, file: File) -> None:
        await FileModel.update_or_create(id=file.id, defaults={
            "name": file.name, "file_type": file.file_type.value, "size": file.size,
            "modified": file.modified, "parent_folder_id": file.parent_folder, "path": file.path,
            "tags": file.tags,
        })

    async def delete(self, file_id: str) -> None:
        await self._delete(file_id)

    async def _delete(self, file_id: str) -> None:
        await FileModel.filter(id=file_id).delete()

    async def delete_batch(self, file_ids: list[str]) -> None:
        await self._delete_batch(file_ids)

    async def _delete_batch(self, file_ids: list[str]) -> None:
        if file_ids:
            await FileModel.filter(id__in=file_ids).delete()

    async def exists_by_path(self, path: str) -> bool:
        return await self._exists_by_path(path)

    async def _exists_by_path(self, path: str) -> bool:
        return await FileModel.filter(path=path).exists()

    async def get_batch(self, file_ids: list[str]) -> dict[str, File]:
        return await self._get_batch(file_ids)

    async def _get_batch(self, file_ids: list[str]) -> dict[str, File]:
        if not file_ids:
            return {}
        models = await FileModel.filter(id__in=file_ids)
        return {model.id: _to_entity(model) for model in models}

    async def get_filtered_files(
        self,
        name_query: str | None = None,
        min_size: float | None = None,
        max_size: float | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[File]:
        query = FileModel.filter(recycle_item__isnull=True)

        if name_query:
            query = query.filter(name__icontains=name_query)

        if min_size is not None:
            query = query.filter(size__gte=min_size)

        if max_size is not None:
            query = query.filter(size__lte=max_size)

        if start_date:
            start_datetime = datetime.fromisoformat(start_date)
            query = query.filter(created_at__gte=start_datetime)

        if end_date:
            end_datetime = datetime.fromisoformat(end_date)
            query = query.filter(created_at__lte=end_datetime)

        models = await query
        return [_to_entity(model) for model in models]
