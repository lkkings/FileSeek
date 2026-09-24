"""Recent access Pydantic schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RecentAccessResponse(BaseModel):
    """最近访问响应。"""

    file_id: str = Field(alias="file_id")
    accessed_at: str = Field(alias="accessed_at")
