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
