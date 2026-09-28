"""Tasks feature 的 Tortoise 仓储实现。"""

from tortoise.transactions import in_transaction
from tortoise.functions import Count

from fileseek.features.library.domain.entities import File
from fileseek.features.tasks.domain.entities import Task, TaskStage, TaskStatus
from fileseek.features.tasks.domain.repositories import TaskRepository
from fileseek.infrastructure.database.models import FileModel, TaskModel
from fileseek.shared.domain.file_types import FileType,FileCategory


def _file_to_entity(model: FileModel) -> File:
    return File(
        id=model.id,
        name=model.name,
        file_type=FileType(model.file_type),
        size=model.size,
        modified=model.modified,
        category=FileCategory(model.category),
        folder_id=model.folder_id,
        path=model.path,
        tags=[tag.name for tag in model.tags],
    )


def _to_entity(model: TaskModel) -> Task:
    return Task(
        id=model.id,
        file=_file_to_entity(model.file) if model.file else None,
        metadata=dict(model.metadata or {}),
        status=TaskStatus(model.status),
        progress=model.progress,
        stage=TaskStage(model.stage) if model.stage else None,
        error_message=model.error_message,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class TaskRepositoryImpl(TaskRepository):
    async def get_by_id(self, task_id: str) -> Task | None:
        model = (
            await TaskModel
            .filter(id=task_id)
            .prefetch_related("file", "file__tags")
            .first()
        )

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
            await query
            .prefetch_related("file", "file__tags")
            .order_by("-created_at")
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        return [_to_entity(model) for model in models], total

    async def count_by_status(self) -> dict[TaskStatus, int]:
        rows = await (
            TaskModel
            .all()
            .group_by("status")
            .annotate(count=Count("id"))
            .values("status", "count")
        )

        counts = {
            status: 0
            for status in TaskStatus
        }

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
                "progress": task.progress,
                "stage": task.stage.value if task.stage else None,
                "error_message": task.error_message,
            },
        )

        task_model.metadata = {
            **(task_model.metadata or {}),
            **(task.metadata or {}),
        }
        await task_model.save(update_fields=["metadata"])

    async def delete(self, task_id: str) -> bool:
        deleted = (
            await TaskModel
            .filter(id=task_id)
            .exclude(status=TaskStatus.PROCESSING.value)
            .delete()
        )
        return deleted > 0


    async def claim_next_queued(self) -> Task | None:
        async with in_transaction() as connection:
            model = (
                await TaskModel
                .filter(status=TaskStatus.QUEUED.value)
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
