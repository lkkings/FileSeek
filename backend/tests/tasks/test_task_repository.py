from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast

from fileseek.features.tasks.domain.entities import TaskStatus
from fileseek.features.tasks.infrastructure.repositories import _to_entity
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
