"""Search feature HTTP 请求/响应模型。

搜索结果数据模型；HTTP 信封统一使用 `fileseek.shared.envelope`。
"""

from __future__ import annotations

from typing import Literal,Any

from pydantic import BaseModel, Field,ConfigDict

class FileItem(BaseModel):
    """向量命中的文件基础信息。"""

    file_id: str
    file_name: str
    file_type: str
    category: str
    path: str
    size: int | None = None
    modified: str | None = None
    tags: list[str] = []
    score: float = 0
    metadata: dict[str, Any] | None = None
    chunks: list[Any] | None = None

    model_config = ConfigDict(from_attributes=True)
class SearchRequest(BaseModel):
    """搜索请求。"""

    query: str = Field(..., description="可选的自然语言查询")
    folder_id: str | None = Field(None, description="文件夹ID，为空则表示全部文件夹")

    categories: list[str] = Field(
        default_factory=lambda: ["document", "image", "video"],
        description="媒体类型过滤：document / image / video",
    )

    tag: str | None = Field(None, description="文件标签，例如（旅游，游戏）")
    name_query: str | None = Field(None, description="文件名子串匹配")

    min_size_m: float | None = Field(None, ge=0, description="最小体积 (MB)")
    max_size_m: float | None = Field(None, ge=0, description="最大体积 (MB)")

    start_date: str | None = Field(None, description="开始日期 YYYY-MM-DD")
    end_date: str | None = Field(None, description="结束日期 YYYY-MM-DD")

    sort_by: Literal["relevance", "created_at", "size"] = Field(
        "relevance",
        description="排序字段：relevance / created_at / size",
    )
    sort_order: Literal["asc", "desc"] = Field(
        "desc",
        description="排序方向：asc / desc",
    )

    page_number: int = Field(1, ge=1, description="页码")
    page_size: int = Field(20, ge=1, description="每页大小")

class SearchResponse(BaseModel):
    """通用分页响应"""

    items: list[FileItem] = Field(
        default_factory=list,
        description="当前页数据",
    )

    page_number: int = Field(
        default=1,
        ge=1,
        description="页码，从 1 开始",
    )

    page_size: int = Field(
        default=20,
        ge=1,
        description="每页大小",
    )

    counter: dict[str,int] =  Field(
        ...,
        description="每种文件数量的统计",
    )

    total: int = Field(
        ge=0,
        description="全部数量",
    )


    has_more: bool = Field(
        default=False,
        description="是否还有更多数据",
    )

