"""Settings Pydantic schemas。

对应 dosc/api-documentation.md 第 5 节：系统设置与 NAS 存储 API。
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SettingsUpdateRequest(BaseModel):
    """修改存储根路径请求。"""

    lib_root: str = Field(alias="lib_root")


class SettingsResponse(BaseModel):
    """系统设置响应。"""

    lib_root: str = Field(alias="lib_root")
    nas_enabled: bool = Field(alias="nas_enabled")

    class Config:
        populate_by_name = True
