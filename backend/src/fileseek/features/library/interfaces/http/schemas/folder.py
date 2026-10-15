"""Folder Pydantic schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class FolderCreateRequest(BaseModel):
    """创建文件夹请求。"""

    name: str
    icon_type: str
    description: str = ""


class FolderUpdateRequest(BaseModel):
    """更新文件夹请求。"""

    name: str
    icon_type: str
    description: str = ""


class FolderResponse(BaseModel):
    """文件夹响应。"""

    id: str
    name: str
    icon_type: str
    description: str
    modified: str
    file_count: int

    class Config:
        populate_by_name = True


class FolderSourceBindingCreateRequest(BaseModel):
    """Create a folder source binding request."""

    storage_id: str = Field(min_length=1)
    path: str = Field(min_length=1)
    recursive: bool = True
    enabled: bool = True


class FolderSourceBindingUpdateRequest(BaseModel):
    """Update a folder source binding request."""

    storage_id: str = Field(min_length=1)
    path: str = Field(min_length=1)
    recursive: bool = True
    enabled: bool = True


class FolderSourceBindingResponse(BaseModel):
    """Folder source binding response."""

    id: str
    folder_id: str
    storage_id: str
    source_path: str
    recursive: bool
    enabled: bool
    watch_status: str
    last_error: str | None
    last_error_at: str | None
