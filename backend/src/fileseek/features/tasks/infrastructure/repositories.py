"""Tasks feature 的 Tortoise 仓储实现。"""

import json

from fileseek.features.tasks.domain.entities import Task, TaskStage, TaskStatus
from fileseek.features.tasks.domain.repositories import TaskRepository
from fileseek.infrastructure.database.models import TaskModel


def _to_entity(model: TaskModel) -> Task:
    return Task(id=model.id, source_path=model.source_path, status=TaskStatus(model.status),
        progress=model.progress, stage=TaskStage(model.stage) if model.stage else None,
        error_message=model.error_message, created_at=model.created_at,
        updated_at=model.updated_at)


class TaskRepositoryImpl(TaskRepository):
    async def get_by_id(self, task_id: str) -> Task | None:
        return await self._get_by_id(task_id)

    async def _get_by_id(self, task_id: str) -> Task | None:
        model = await TaskModel.get_or_none(id=task_id)
        return _to_entity(model) if model else None

    async def list_all(self, status: str | None, page: int, page_size: int) -> tuple[list[Task], int]:
        return await self._list_all(status, page, page_size)

    async def _list_all(self, status: str | None, page: int, page_size: int) -> tuple[list[Task], int]:
        query = TaskModel.all()
        if status is not None:
            query = query.filter(status=status)
        total = await query.count()
        models = await query.order_by("created_at").offset((page - 1) * page_size).limit(page_size)
        return [_to_entity(model) for model in models], total

    async def save(self, task: Task) -> None:
        await self._save(task)

    async def _save(self, task: Task) -> None:
        await TaskModel.update_or_create(id=task.id, defaults={
            "source_path": task.source_path, "status": task.status.value, "progress": task.progress,
            "stage": task.stage.value if task.stage else None,
            "error_message": task.error_message,
            "created_at": task.created_at, "updated_at": task.updated_at
        })

    async def claim_next_queued(self) -> Task | None:
        return await self._claim_next_queued()

    async def _claim_next_queued(self) -> Task | None:
        model = await TaskModel.filter(status=TaskStatus.QUEUED.value).order_by(
            "created_at"
        ).first()
        if model is None:
            return None
        model.status = TaskStatus.PROCESSING.value
        await model.save(update_fields=["status", "updated_at"])
        return _to_entity(model)
