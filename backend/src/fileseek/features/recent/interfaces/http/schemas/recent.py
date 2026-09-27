"""Recent access Pydantic schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field

from fileseek.features.library.interfaces.http.schemas.file import FileResponse


class RecentAccessResponse(BaseModel):
    """最近访问响应。"""

    id: int = Field(alias="id")
    file_id: str = Field(alias="file_id")
    accessed_at: str = Field(alias="accessed_at")
    file: FileResponse | None = Field(default=None, alias="file")


class RecentAccessPageResponse(BaseModel):
    """最近访问分页响应。"""

    items: list[RecentAccessResponse] = Field(
        default_factory=list,
        description="当前页数据",
    )

    page_number: int = Field(default=1, ge=1, description="页码，从 1 开始")

    page_size: int = Field(default=20, ge=1, description="每页大小")

    total: int = Field(ge=0, description="全部数量")

    has_more: bool = Field(default=False, description="是否还有更多数据")


class RecordAccessRequest(BaseModel):
    """添加最近访问记录请求。"""

    file_id: str = Field(alias="file_id")
