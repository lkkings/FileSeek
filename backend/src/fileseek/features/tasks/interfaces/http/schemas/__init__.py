from pydantic import BaseModel


class TaskResponse(BaseModel):
    id: str
    source_path: str
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
    pagination: dict[str, int]

