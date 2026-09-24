"""Folder Pydantic schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class FolderCreateRequest(BaseModel):
    """创建文件夹请求。"""

    name: str
    iconType: str = Field(alias="iconType")
    description: str = ""


class FolderUpdateRequest(BaseModel):
    """更新文件夹请求。"""

    name: str
    iconType: str = Field(alias="iconType")
    description: str = ""


class FolderResponse(BaseModel):
    """文件夹响应。"""

    id: str
    name: str
    iconType: str = Field(alias="iconType")
    description: str
    modified: str
    file_count: int = Field(alias="file_count")

    class Config:
        populate_by_name = True
