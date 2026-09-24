"""NAS Pydantic schemas。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class NASTestRequest(BaseModel):
    """NAS 连通性测试请求。"""

    protocol: str
    host: str
    share_path: str = Field(alias="share_path")
    username: str
    password: str

    class Config:
        populate_by_name = True
