from __future__ import annotations

from fileseek.features.library.application.dto import ImportTaskSnapshotDTO
from fileseek.features.tasks.domain.entities import Task
from fileseek.features.tasks.domain.repositories import TaskRepository


class TaskRepositoryImportProgressPort:
    def __init__(self, repository: TaskRepository) -> None:
        self.repository = repository

    async def get_snapshots(
        self,
        task_ids: tuple[str, ...],
    ) -> dict[str, ImportTaskSnapshotDTO]:
        snapshots: dict[str, ImportTaskSnapshotDTO] = {}
        for task_id in task_ids:
            task = await self.repository.get_by_id(task_id)
            if task is None:
                continue
            snapshots[task_id] = self._to_snapshot(task)
        return snapshots

    @staticmethod
    def _to_snapshot(task: Task) -> ImportTaskSnapshotDTO:
        return ImportTaskSnapshotDTO(
            task_id=task.id,
            file_id=task.file.id if task.file else None,
            status=task.status.value,
            progress=task.progress,
            stage=task.stage.value if task.stage else None,
            error_message=task.error_message,
        )
