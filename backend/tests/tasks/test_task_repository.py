from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from fileseek.config.settings import Settings
from fileseek.features.tasks.domain.entities import TaskStatus
from fileseek.features.tasks.infrastructure.repositories import (
    TaskRepositoryImpl,
    _to_entity,
)
from fileseek.infrastructure.database.models import FileModel, TaskModel
from fileseek.shared.domain.file_types import FileCategory, FileType


def test_task_repository_maps_file_model_to_domain_file() -> None:
    file_model = cast(
        FileModel,
        SimpleNamespace(
            id="file-1",
            name="document.txt",
            file_type=FileType.TXT.value,
            category=FileCategory.DOCUMENT.value,
            size=1,
            modified=datetime.now(UTC),
            path="/documents/document.txt",
            tags=[],
        ),
    )
    task_model = cast(
        TaskModel,
        SimpleNamespace(
            id="task-1",
            file=file_model,
            metadata={},
            status=TaskStatus.QUEUED.value,
            completed_count=3,
            total_count=9,
            stage=None,
            error_message=None,
            created_at=None,
            updated_at=None,
        ),
    )

    task = _to_entity(task_model)

    assert task.file.file_type is FileType.TXT
    assert task.file.category is FileCategory.DOCUMENT
    assert task.file.path == "/documents/document.txt"
    assert task.completed_count == 3
    assert task.total_count == 9
    assert not hasattr(task, "progress")


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
async def test_repository_bulk_cancel_incomplete_covers_all_pages_and_statuses(
    settings: Settings,
) -> None:
    repository = TaskRepositoryImpl()

    for index in range(52):
        await _create_task(f"queued-{index}", TaskStatus.QUEUED, settings.lib_root)
    await _create_task("processing-1", TaskStatus.PROCESSING, settings.lib_root)
    await _create_task("cancelled-1", TaskStatus.CANCELLED, settings.lib_root)
    await _create_task("failed-1", TaskStatus.FAILED, settings.lib_root)
    await _create_task("completed-1", TaskStatus.COMPLETED, settings.lib_root)

    cancelled_count, processing_ids = await repository.cancel_incomplete()

    assert cancelled_count == 53
    assert processing_ids == ("processing-1",)
    assert await TaskModel.filter(status=TaskStatus.CANCELLED.value).count() == 54
    assert await TaskModel.filter(status=TaskStatus.QUEUED.value).count() == 0
    assert await TaskModel.filter(status=TaskStatus.PROCESSING.value).count() == 0
    assert await TaskModel.filter(status=TaskStatus.FAILED.value).count() == 1
    assert await TaskModel.filter(status=TaskStatus.COMPLETED.value).count() == 1


@pytest.mark.asyncio
async def test_repository_bulk_continue_cancelled_clears_retry_progress(
    settings: Settings,
) -> None:
    repository = TaskRepositoryImpl()

    await _create_task("cancelled-1", TaskStatus.CANCELLED, settings.lib_root)
    await _create_task("queued-1", TaskStatus.QUEUED, settings.lib_root)
    await _create_task("processing-1", TaskStatus.PROCESSING, settings.lib_root)
    await _create_task("failed-1", TaskStatus.FAILED, settings.lib_root)
    await _create_task("completed-1", TaskStatus.COMPLETED, settings.lib_root)
    await TaskModel.filter(id="cancelled-1").update(
        error_message="任务已终止",
        completed_count=2,
        total_count=9,
    )

    continued_count = await repository.continue_cancelled()

    assert continued_count == 1
    cancelled_task = await TaskModel.get(id="cancelled-1")
    assert cancelled_task.status == TaskStatus.QUEUED.value
    assert cancelled_task.error_message is None
    assert cancelled_task.completed_count is None
    assert cancelled_task.total_count is None
    assert await TaskModel.filter(status=TaskStatus.QUEUED.value).count() == 2
    assert await TaskModel.filter(status=TaskStatus.PROCESSING.value).count() == 1
    assert await TaskModel.filter(status=TaskStatus.FAILED.value).count() == 1
    assert await TaskModel.filter(status=TaskStatus.COMPLETED.value).count() == 1


@pytest.mark.asyncio
async def test_repository_bulk_delete_completed_preserves_files(
    settings: Settings,
) -> None:
    repository = TaskRepositoryImpl()

    await _create_task("completed-1", TaskStatus.COMPLETED, settings.lib_root)
    await _create_task("completed-2", TaskStatus.COMPLETED, settings.lib_root)
    await _create_task("queued-1", TaskStatus.QUEUED, settings.lib_root)
    await _create_task("failed-1", TaskStatus.FAILED, settings.lib_root)

    deleted_count = await repository.delete_completed()

    assert deleted_count == 2
    assert await TaskModel.filter(status=TaskStatus.COMPLETED.value).count() == 0
    assert await TaskModel.filter(id__in=["queued-1", "failed-1"]).count() == 2
    assert await FileModel.filter(id__in=["file-completed-1", "file-completed-2"]).count() == 2
