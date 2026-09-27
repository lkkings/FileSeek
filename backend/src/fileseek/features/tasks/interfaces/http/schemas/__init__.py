from pydantic import BaseModel

from fileseek.features.tasks.application.dto import FileDTO


class TaskResponse(BaseModel):
    id: str
    file: FileDTO
    status: str
    progress: int
    stage: str | None
    error_message: str | None
    created_at: str


class TaskListResponse(BaseModel):
    tasks: list[TaskResponse]
    counts: dict[str, int]
    page: int
    page_size: int
    total: int

