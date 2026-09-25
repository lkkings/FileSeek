"""Recycle bin Pydantic schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RecycleItemResponse(BaseModel):
    """回收站条目响应。"""

    id: str
    original_file_id: str = Field(alias="original_file_id")
    original_name: str = Field(alias="original_name")
    original_path: str = Field(alias="original_path")
    deleted_at: str = Field(alias="deleted_at")
    file_type: str = Field(alias="file_type")
    size: str
