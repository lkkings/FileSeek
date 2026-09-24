from fileseek.features.tasks.application.dto import TaskDTO
from fileseek.features.tasks.domain.entities import Task



def task_to_dto(task: Task) -> TaskDTO:
    return TaskDTO(
        id=task.id,
        source_path=task.source_path,
        status=task.status.value,
        progress=task.progress,
        stage=task.stage.value if task.stage else None,
        error_message=task.error_message,
        created_at=task.created_at,
    )
