"""Search feature HTTP 请求/响应模型。

响应形状不走 `shared.envelope`：契约要求 `error` 是 `{code, message}` 对象，而共享
envelope 的 `error` 是字符串。所以这里自带一个同名字段但结构更细的信封。
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    """搜索请求。"""

    # 空串/纯空白的校验放在路由层做：在这里用 field_validator 抛错会被 FastAPI 收敛成
    # 422 的字段级报错，返回不出契约要求的 INVALID_QUERY 形状。
    query: str = Field(..., description="自然语言查询，必须含至少一个非空白字符")
    file_types: list[str] = Field(
        default_factory=lambda: ["document", "image", "video"],
        description="媒体类型过滤：document / image / video",
    )
    limit: int = Field(20, ge=1, description="每种媒体类型各自返回的 Top N 数量")
    name_query: str | None = Field(None, description="文件名子串匹配")
    min_size_m: float | None = Field(None, ge=0, description="最小体积 (MB)")
    max_size_m: float | None = Field(None, ge=0, description="最大体积 (MB)")
    start_date: str | None = Field(None, description="开始日期 YYYY-MM-DD")
    end_date: str | None = Field(None, description="结束日期 YYYY-MM-DD")


class SearchResultBase(BaseModel):
    """三种媒体类型结果的公共字段。"""

    file_id: str
    filename: str
    preview_url: str
    score: float
    path: str
    accessible: bool


class DocumentSearchResult(SearchResultBase):
    """文档结果：额外带命中文本及其位置。"""

    matched_text: str = ""
    page_number: int | None = None
    line_number: int | None = None


class ImageSearchResult(SearchResultBase):
    """图片结果：只有公共字段。"""


class VideoSearchResult(SearchResultBase):
    """视频结果：额外带命中片段的起止时间（秒）。"""

    start_time: int | None = None
    end_time: int | None = None


class SearchResponseData(BaseModel):
    """按媒体类型分组的搜索结果。某类无命中时为空数组。"""

    documents: list[DocumentSearchResult] = Field(default_factory=list)
    images: list[ImageSearchResult] = Field(default_factory=list)
    videos: list[VideoSearchResult] = Field(default_factory=list)


class SearchError(BaseModel):
    """错误信息。"""

    code: str
    message: str


class SearchResponse(BaseModel):
    """搜索响应信封。"""

    status: str = "success"
    data: SearchResponseData | None = None
    error: SearchError | None = None
