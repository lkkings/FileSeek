"""Search feature HTTP 请求/响应模型。

搜索结果数据模型；HTTP 信封统一使用 `fileseek.shared.envelope`。
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from fileseek.features.search.application.contracts import SearchRequest as SearchRequest


class EnhancedSearchRequest(BaseModel):
    """Retrieval-augmented search request."""

    query: str = Field(..., description="用户的自然语言描述")
    folder_id: str | None = Field(None, description="文件夹ID，为空则表示全部文件夹")
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


class FileItem(BaseModel):
    """向量命中的文件基础信息。"""

    file_id: str
    file_name: str
    file_type: str
    category: str
    path: str
    size: int | None = None
    modified: str | None = None
    tags: list[str] = Field(default_factory=list)
    score: float = 0
    metadata: dict[str, Any] = Field(default_factory=dict)
    chunks: list[Any] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


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

    counter: dict[str, int] = Field(
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


class EnhancedSearchProgressEvent(BaseModel):
    """One round-level progress event from an enhanced-search stream."""

    model_config = ConfigDict(extra="forbid")

    type: Literal[
        "status",
        "reasoning",
        "tool_call",
        "tool_result",
        "result",
        "error",
    ]
    phase: str | None = None
    message: str | None = None
    round_number: int | None = None
    content: str | None = None
    tool_name: str | None = None
    query: str | None = None
    categories: list[str] = Field(default_factory=list)
    name_query: str | None = None
    candidate_count: int | None = None
    total: int | None = None
    result: SearchResponse | None = None
    error: str | None = None
