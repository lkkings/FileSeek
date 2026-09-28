"""File Pydantic schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class FileResponse(BaseModel):
    """文件响应。"""

    id: str
    name: str
    file_type: str
    category: str
    size: str
    modified: str
    folder_id: str | None
    path: str


class BatchImportItemRequest(BaseModel):
    path: str = Field(min_length=1)
    storage_id: str = Field(default="local", alias="storage_id")

    model_config = ConfigDict(populate_by_name=True)


class BatchImportRequest(BaseModel):
    folder_id: str = Field(min_length=1, alias="folder_id")
    items: list[BatchImportItemRequest] = Field(min_length=1)

    model_config = ConfigDict(populate_by_name=True)


class BatchImportResponse(BaseModel):
    import_id: str = Field(alias="import_id")
    total: int


class MoveFilesRequest(BaseModel):
    """批量移动文件请求。"""

    file_ids: list[str] = Field(min_length=1, alias="file_ids")
    target_folder_id: str = Field(min_length=1, alias="target_folder_id")


class MoveFilesResponse(BaseModel):
    """批量移动文件响应。"""

    moved_count: int = Field(alias="moved_count")
