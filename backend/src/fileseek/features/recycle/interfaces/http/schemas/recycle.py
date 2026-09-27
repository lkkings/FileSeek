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


class RecycleItemPageResponse(BaseModel):
    """回收站分页响应。"""

    items: list[RecycleItemResponse] = Field(
        default_factory=list,
        description="当前页数据",
    )

    page_number: int = Field(default=1, ge=1, description="页码，从 1 开始")

    page_size: int = Field(default=20, ge=1, description="每页大小")

    total: int = Field(ge=0, description="全部数量")

    has_more: bool = Field(default=False, description="是否还有更多数据")


class AddFiles2RecycleRequest(BaseModel):
    """批量将文件移入回收站请求。"""

    file_ids: list[str]


class RestoreRecycleRequest(BaseModel):
    """批量还原回收站条目请求。"""

    item_ids: list[str]


class DeleteRecycleRequest(BaseModel):
    """批量永久删除回收站条目请求。"""

    item_ids: list[str]

