"""Folder Pydantic schemas."""

from __future__ import annotations

from pydantic import BaseModel


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
