"""File Pydantic schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


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


class FileImportRequest(BaseModel):
    """单文件入库请求。"""

    folder_id: str  = Field(..., alias="folder_id")
    path: str = Field(alias="path")


class FileImportResponse(BaseModel):
    """单文件入库响应。"""

    file_id: str = Field(alias="file_id")


class MoveFilesRequest(BaseModel):
    """批量移动文件请求。"""

    file_ids: list[str] = Field(min_length=1, alias="file_ids")
    target_folder_id: str = Field(min_length=1, alias="target_folder_id")


class MoveFilesResponse(BaseModel):
    """批量移动文件响应。"""

    moved_count: int = Field(alias="moved_count")
