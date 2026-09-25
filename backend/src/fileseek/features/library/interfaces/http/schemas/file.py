"""File Pydantic schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class FileResponse(BaseModel):
    """文件响应。"""

    id: str
    name: str
    FileType: str = Field(alias="FileType")
    size: str
    modified: str
    parentFolder: str | None = Field(alias="parentFolder")
    path: str


class FileBatchDeleteRequest(BaseModel):
    """批量删除文件请求。"""

    file_ids: list[str] = Field(alias="file_ids")


class FileAddRequest(BaseModel):
    """添加文件请求（导入任务提交）。"""

    parent_folder: str | None = Field(None, alias="parent_folder")
    path_input: str = Field(alias="path_input")
    batch_import_folder: bool = Field(False, alias="batch_import_folder")


class FileImportRequest(BaseModel):
    """单文件入库请求。"""

    folder_id: str  = Field(..., alias="folder_id")
    path: str = Field(alias="path")


class FileImportResponse(BaseModel):
    """单文件入库响应。"""

    file_id: str = Field(alias="file_id")
