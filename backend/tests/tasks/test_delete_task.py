from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from fileseek.features.tasks.application.manager import DefaultTaskManager
from fileseek.features.tasks.domain.entities import TaskStatus
from fileseek.features.tasks.infrastructure.repositories import TaskRepositoryImpl
from fileseek.infrastructure.database.models import FileModel, TaskModel
from fileseek.shared.domain.file_types import FileCategory, FileType


async def _create_task(
    task_id: str,
    status: TaskStatus,
    root: Path,
) -> None:
    await FileModel.create(
        id=f"file-{task_id}",
        name=f"{task_id}.txt",
        file_type=FileType.TXT.value,
        category=FileCategory.DOCUMENT.value,
        size=1,
        modified=datetime.now(UTC),
        path=str(root / f"{task_id}.txt"),
        storage_id="local",
        access_state="available",
    )
    await TaskModel.create(
        id=task_id,
        file_id=f"file-{task_id}",
        status=status.value,
    )


@pytest.mark.asyncio
async def test_delete_task_removes_non_processing_task(settings) -> None:
    await _create_task("task-queued", TaskStatus.QUEUED, settings.lib_root)
    manager = DefaultTaskManager(TaskRepositoryImpl())

    await manager.delete("task-queued")

    assert await TaskModel.filter(id="task-queued").exists() is False


@pytest.mark.asyncio
async def test_delete_task_rejects_processing_task(settings) -> None:
    from fileseek.features.tasks.domain.exceptions import InvalidTransitionError

    await _create_task("task-processing", TaskStatus.PROCESSING, settings.lib_root)
    manager = DefaultTaskManager(TaskRepositoryImpl())

    with pytest.raises(InvalidTransitionError):
        await manager.delete("task-processing")

    assert await TaskModel.filter(id="task-processing").exists() is True
