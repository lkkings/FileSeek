from fileseek.features.library.domain.entities import File
from fileseek.features.tasks.application.dto import FileDTO, TaskDTO
from fileseek.features.tasks.domain.entities import Task


def _progress_value(task: Task) -> str:
    if (
        task.completed_count is None
        or task.total_count is None
        or task.total_count <= 0
        or task.completed_count < 0
        or task.completed_count > task.total_count
    ):
        return task.status.value
    return f"{task.completed_count}/{task.total_count}"


def file_to_dto(file: File) -> FileDTO:
    return FileDTO(
        id=file.id,
        name=file.name,
        path=file.path,
        size=file.size,
        file_type=file.file_type.value,
        modified=file.modified.isoformat(),
    )


def task_to_dto(task: Task) -> TaskDTO:
    return TaskDTO(
        id=task.id,
        file=file_to_dto(task.file) if task.file else None,
        status=task.status.value,
        progress=_progress_value(task),
        completed_count=task.completed_count,
        total_count=task.total_count,
        stage=task.stage.value if task.stage else None,
        error_message=task.error_message,
        created_at=task.created_at.isoformat(),
        updated_at=task.updated_at.isoformat(),
    )
