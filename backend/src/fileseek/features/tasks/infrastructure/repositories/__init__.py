"""Tasks feature 的 Tortoise 仓储实现。"""

from typing import cast

from tortoise.functions import Count
from tortoise.transactions import in_transaction

from fileseek.features.library.domain.entities import File
from fileseek.features.tasks.domain.entities import Task, TaskStage, TaskStatus
from fileseek.features.tasks.domain.repositories import TaskRepository
from fileseek.infrastructure.database.models import FileModel, TaskModel
from fileseek.shared.domain.file_types import FileCategory, FileType


def _file_to_entity(model: FileModel) -> File:
    return File(
        id=model.id,
        name=model.name,
        file_type=FileType(model.file_type),
        size=model.size,
        modified=model.modified,
        category=FileCategory(model.category),
        folder_id=cast(str | None, getattr(model, "folder_id", None)),
        path=model.path,
        tags=[tag.name for tag in model.tags],
    )


def _to_entity(model: TaskModel) -> Task:
    file_model = model.file
    if file_model is None:
        raise ValueError(f"任务 {model.id} 缺少关联文件")

    return Task(
        id=model.id,
        file=_file_to_entity(file_model),
        metadata=dict(model.metadata or {}),
        status=TaskStatus(model.status),
        completed_count=model.completed_count,
        total_count=model.total_count,
        stage=TaskStage(model.stage) if model.stage else None,
        error_message=model.error_message,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class TaskRepositoryImpl(TaskRepository):
    async def get_by_id(self, task_id: str) -> Task | None:
        model = await TaskModel.filter(id=task_id).prefetch_related("file", "file__tags").first()

        return _to_entity(model) if model else None

    async def list_all(
        self,
        status: TaskStatus | None,
        page: int,
        page_size: int,
    ) -> tuple[list[Task], int]:
        query = TaskModel.all()

        if status is not None:
            query = query.filter(status=status.value)

        total = await query.count()

        models = (
            await query.prefetch_related("file", "file__tags")
            .order_by("-created_at")
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        return [_to_entity(model) for model in models], total

    async def count_by_status(self) -> dict[TaskStatus, int]:
        rows = await (
            TaskModel.all().group_by("status").annotate(count=Count("id")).values("status", "count")
        )

        counts = dict.fromkeys(TaskStatus, 0)

        for row in rows:
            status = TaskStatus(row["status"])
            counts[status] = row["count"]

        return counts

    async def save(self, task: Task) -> None:
        task_model, _ = await TaskModel.update_or_create(
            id=task.id,
            defaults={
                "file_id": task.file.id if task.file else None,
                "status": task.status.value,
                "completed_count": task.completed_count,
                "total_count": task.total_count,
                "stage": task.stage.value if task.stage else None,
                "error_message": task.error_message,
            },
        )

        task_model.metadata = {
            **(task_model.metadata or {}),
            **(task.metadata or {}),
        }
        await task_model.save(update_fields=["metadata"])

    async def cancel(self, task_id: str) -> Task | None:
        """原子地把处理中的任务标记为已终止。"""
        async with in_transaction() as connection:
            model = (
                await TaskModel.filter(id=task_id)
                .using_db(connection)
                .select_for_update()
                .get_or_none()
            )

            if model is None or model.status != TaskStatus.PROCESSING.value:
                return None

            model.status = TaskStatus.CANCELLED.value
            model.error_message = "任务已终止"
            await model.save(
                using_db=connection,
                update_fields=["status", "error_message", "updated_at"],
            )
            await model.fetch_related("file", "file__tags")
            return _to_entity(model)

    async def cancel_incomplete(self) -> tuple[int, tuple[str, ...]]:
        """批量把 queued/processing 任务原子地标记为已终止。"""
        async with in_transaction() as connection:
            models = (
                await TaskModel.filter(
                    status__in=(
                        TaskStatus.QUEUED.value,
                        TaskStatus.PROCESSING.value,
                    ),
                )
                .using_db(connection)
                .select_for_update()
            )
            processing_ids = tuple(
                model.id for model in models if model.status == TaskStatus.PROCESSING.value
            )

            for model in models:
                model.status = TaskStatus.CANCELLED.value
                model.error_message = "任务已终止"
                await model.save(
                    using_db=connection,
                    update_fields=["status", "error_message", "updated_at"],
                )

            return len(models), processing_ids

    async def continue_cancelled(self) -> int:
        """批量把 cancelled 任务原子地恢复为 queued。"""
        async with in_transaction() as connection:
            models = (
                await TaskModel.filter(status=TaskStatus.CANCELLED.value)
                .using_db(connection)
                .select_for_update()
            )

            for model in models:
                model.update_from_dict(
                    {
                        "status": TaskStatus.QUEUED.value,
                        "error_message": None,
                        "completed_count": None,
                        "total_count": None,
                    }
                )
                await model.save(
                    using_db=connection,
                    update_fields=[
                        "status",
                        "error_message",
                        "completed_count",
                        "total_count",
                        "updated_at",
                    ],
                )

            return len(models)

    async def delete_completed(self) -> int:
        """批量删除 completed 任务，保留关联文件。"""
        async with in_transaction() as connection:
            models = (
                await TaskModel.filter(status=TaskStatus.COMPLETED.value)
                .using_db(connection)
                .select_for_update()
            )

            for model in models:
                await model.delete(using_db=connection)

            return len(models)

    async def delete(self, task_id: str) -> bool:
        async with in_transaction() as connection:
            task_model = (
                await TaskModel.filter(id=task_id)
                .using_db(connection)
                .select_for_update()
                .get_or_none()
            )

            if task_model is None or task_model.status == TaskStatus.PROCESSING.value:
                return False

            if task_model.status == TaskStatus.COMPLETED.value:
                await task_model.delete(using_db=connection)
                return True

            file_model = (
                await FileModel.filter(id=cast(str, getattr(task_model, "file_id", None)))
                .using_db(connection)
                .get_or_none()
            )

            if file_model is not None:
                await file_model.delete(using_db=connection)
                return True

            await task_model.delete(using_db=connection)
            return True

    async def claim_next_queued(self) -> Task | None:
        async with in_transaction() as connection:
            model = (
                await TaskModel.filter(status=TaskStatus.QUEUED.value)
                .prefetch_related("file", "file__tags")
                .using_db(connection)
                .select_for_update()
                .order_by("created_at")
                .first()
            )

            if model is None:
                return None

            model.status = TaskStatus.PROCESSING.value

            await model.save(
                using_db=connection,
                update_fields=["status", "updated_at"],
            )

            # 事务连接下重新加载关联 File。
            await model.fetch_related("file", "file__tags")

            return _to_entity(model)
