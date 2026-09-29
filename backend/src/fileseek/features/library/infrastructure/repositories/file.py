"""Library 文件的 Tortoise 仓储实现。"""

from collections.abc import Sequence
from datetime import UTC, datetime, time

from tortoise.queryset import QuerySet
from tortoise.transactions import in_transaction

from fileseek.features.library.domain.entities import File, FileChunk
from fileseek.features.library.domain.repositories import FileRepository
from fileseek.infrastructure.database.models import FileModel, TagModel
from fileseek.shared.domain.file_types import FileCategory, FileType
from fileseek.shared.domain.identifiers import generate_id


async def _to_entity(model: FileModel) -> File:
    chunk_models = await model.filechunks.all()
    return File(
        id=model.id,
        name=model.name,
        file_type=FileType(model.file_type),
        category=FileCategory(model.category),
        size=model.size,
        modified=model.modified,
        folder_id=model.folder_id,
        path=model.path,
        storage_id=model.storage_id,
        access_state=model.access_state or "unknown",
        last_checked_at=model.last_checked_at,
        tags=[
            tag.name
            for tag in model.tags
        ],
        chunks=[
            FileChunk(
                id=chunk.id,
                file_id=model.id,
                metadata=chunk.metadata,
            )
            for chunk in chunk_models
        ],
    )



async def _to_entities(models: list[FileModel]) -> list[File]:
    """批量将数据库模型转换为 Domain Entity。"""
    return [await _to_entity(model) for model in models]


class FileRepositoryImpl(FileRepository):
    async def list_tags(self) -> list[str]:
        return await TagModel.all().order_by("name").values_list("name", flat=True)


    async def get_by_id(self, file_id: str) -> File | None:
        return await self._get_by_id(file_id)

    async def _get_by_id(self, file_id: str) -> File | None:
        model = (
            await FileModel
            .filter(id=file_id)
            .prefetch_related("tags","filechunks")
            .first()
        )

        return await _to_entity(model) if model else None

    async def save(self, file: File) -> None:
        await self._save(file)


    async def save_batch(self, files: Sequence[File]) -> None:
        if not files:
            return

        async with in_transaction():
            for file in files:
                await self._save(file)


    async def _save(self, file: File) -> None:
        model, _ = await FileModel.update_or_create(
            id=file.id,
            defaults={
                "name": file.name,
                "file_type": file.file_type.value,
                "category": file.category.value,
                "size": file.size,
                "modified": file.modified,
                "folder_id": file.folder_id,
                "path": file.path,
                "storage_id": file.storage_id,
                "access_state": file.access_state,
                "last_checked_at": file.last_checked_at,
            },
        )

        # ManyToManyField 必须单独维护。
        # file.tags 可以是 tag name 列表。
        if file.tags is not None:

            tag_models = []

            for tag_name in set(file.tags):
                tag_name = tag_name.strip()

                if not tag_name:
                    continue

                tag, _ = await TagModel.get_or_create(
                    name=tag_name,
                    defaults={"id": generate_id("tag")},
                )
                tag_models.append(tag)

            await model.tags.clear()
            if tag_models:
                await model.tags.add(*tag_models)

    async def delete(self, file_id: str) -> None:
        await self._delete(file_id)

    async def set_access_state(
        self,
        file_id: str,
        access_state: str,
    ) -> bool:
        updated = await FileModel.filter(id=file_id).update(
            access_state=access_state,
            last_checked_at=datetime.now(UTC),
        )
        return updated > 0

    async def _delete(self, file_id: str) -> None:
        await FileModel.filter(
            id=file_id,
        ).delete()

    async def delete_batch(self, file_ids: list[str]) -> None:
        await self._delete_batch(file_ids)

    async def _delete_batch(self, file_ids: list[str]) -> None:
        if not file_ids:
            return

        await FileModel.filter(
            id__in=file_ids,
        ).delete()

    async def count_by_category(
        self,
        *,
        name_query: str | None = None,
        tag: str | None = None,
        min_size: float | None = None,
        max_size: float | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        folder_id: str | None = None,
        categories: list[str] | None = None,
    ) -> dict[str, int]:
        from tortoise.functions import Count

        query = self._filtered_query(
            name_query=name_query,
            tag=tag,
            min_size=min_size,
            max_size=max_size,
            start_date=start_date,
            end_date=end_date,
            folder_id=folder_id,
            categories=categories,
        )
        rows = await (
            query
            .group_by("category")
            .annotate(count=Count("id"))
            .values("category", "count")
        )

        counts = {category.value: 0 for category in FileCategory}

        for row in rows:
            counts[row["category"]] = row["count"]

        return counts


    async def count(
        self,
        *,
        name_query: str | None = None,
        tag: str | None = None,
        min_size: float | None = None,
        max_size: float | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        folder_id: str | None = None,
        categories: list[str] | None = None,
    ) -> int:
        return int(
            await self._filtered_query(
                name_query=name_query,
                tag=tag,
                min_size=min_size,
                max_size=max_size,
                start_date=start_date,
                end_date=end_date,
                folder_id=folder_id,
                categories=categories,
            ).count(),
        )

    async def query(
        self,
        name_query: str | None = None,
        tag: str | None = None,
        min_size: float | None = None,
        max_size: float | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        folder_id: str | None = None,
        categories: list[str] | None = None,
        page_number: int = None,
        page_size: int  = None,
        sort_by: str | None = None,
        sort_order: str | None = None,
    ) -> list[File]:

        # =========================
        # 分页参数
        # =========================


        # =========================
        # 基础查询
        # =========================

        query = self._filtered_query(
            name_query=name_query,
            tag=tag,
            min_size=min_size,
            max_size=max_size,
            start_date=start_date,
            end_date=end_date,
            folder_id=folder_id,
            categories=categories,
        )

        # =========================
        # ManyToMany 去重
        # =========================

        if tag:
            query = query.distinct()

        # =========================
        # 排序
        # =========================

        # 对外暴露的排序字段 -> 数据库字段
        allowed_sort_fields = {
            "name": "name",
            "size": "size",
            "created_at": "created_at",
            "updated_at": "updated_at",
        }

        sort_field = allowed_sort_fields.get(
            sort_by or "",
            "created_at",
        )

        sort_direction = (
            sort_order or "desc"
        ).lower()

        if sort_direction not in {"asc", "desc"}:
            sort_direction = "desc"

        order_by = (
            sort_field
            if sort_direction == "asc"
            else f"-{sort_field}"
        )

        # =========================
        # 分页
        # =========================
        if page_size and page_number:
            page_number = max(1, page_number)
            page_size = max(1, min(page_size, 100))
            offset = (page_number - 1) * page_size
            models = (
                await query
                .prefetch_related("tags","filechunks")
                .order_by(
                    order_by,
                    "-id",
                )
                .offset(offset)
                .limit(page_size)
            )
        else:
            models = (
                await query
                .prefetch_related("tags","filechunks")
                .order_by(
                    order_by,
                    "-id",
                )
            )

        return await _to_entities(models)

    def _filtered_query(
        self,
        name_query: str | None,
        tag: str | None,
        min_size: float | None,
        max_size: float | None,
        start_date: str | None,
        end_date: str | None,
        folder_id: str | None,
        categories: list[str] | None,
    ) -> QuerySet[FileModel]:
        query = FileModel.filter(recycle_item__isnull=True)

        if name_query:
            name_query = name_query.strip()

            if name_query:
                query = query.filter(name__icontains=name_query)

        if tag:
            tag = tag.strip()

            if tag:
                query = query.filter(tags__name=tag)

        if min_size is not None:
            query = query.filter(size__gte=min_size)

        if max_size is not None:
            query = query.filter(size__lte=max_size)

        if folder_id:
            folder_id = folder_id.strip()

            if folder_id:
                query = query.filter(folder_id=folder_id)

        if categories:
            categories = [
                category.strip()
                for category in categories
                if category and category.strip()
            ]

            if categories:
                query = query.filter(category__in=categories)

        if start_date:
            query = query.filter(
                created_at__gte=datetime.fromisoformat(start_date),
            )

        if end_date:
            end_datetime = datetime.fromisoformat(end_date)

            if end_datetime.time() == time.min:
                end_datetime = datetime.combine(
                    end_datetime.date(),
                    time.max,
                )

            query = query.filter(created_at__lte=end_datetime)

        return query
