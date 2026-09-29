from __future__ import annotations

from datetime import UTC, datetime

from fileseek.features.library.domain.entities import File
from fileseek.features.tasks.application.mappers import task_to_dto
from fileseek.features.tasks.domain.entities import Task, TaskStage, TaskStatus
from fileseek.shared.domain.file_types import FileCategory, FileType


def _make_task(
    status: TaskStatus,
    completed_count: int | None,
    total_count: int | None,
) -> Task:
    file = File(
        id="file-1",
        name="document.txt",
        file_type=FileType.TXT,
        category=FileCategory.DOCUMENT,
        size=1,
        modified=datetime.now(UTC),
        path="/documents/document.txt",
    )
    return Task(
        id="task-1",
        file=file,
        status=status,
        completed_count=completed_count,
        total_count=total_count,
        stage=TaskStage.ENCODED,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def test_task_to_dto_formats_usable_count_pair() -> None:
    task = _make_task(TaskStatus.PROCESSING, 3, 10)

    dto = task_to_dto(task)

    assert dto.progress == "3/10"
    assert dto.completed_count == 3
    assert dto.total_count == 10


def test_task_to_dto_uses_status_when_count_pair_is_missing() -> None:
    task = _make_task(TaskStatus.PROCESSING, None, None)

    dto = task_to_dto(task)

    assert dto.progress == "processing"
    assert dto.completed_count is None
    assert dto.total_count is None
