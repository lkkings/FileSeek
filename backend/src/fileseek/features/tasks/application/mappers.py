from fileseek.features.library.domain.entities import File
from fileseek.features.tasks.application.dto import FileDTO, TaskDTO
from fileseek.features.tasks.domain.entities import Task


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
        progress=task.progress,
        stage=task.stage.value if task.stage else None,
        error_message=task.error_message,
        created_at=task.created_at.isoformat(),
        updated_at=task.updated_at.isoformat(),
    )