"""Search feature 领域实体。"""

from __future__ import annotations

from dataclasses import dataclass

from fileseek.shared.domain.file_types import FileType


@dataclass
class SearchResult:
    """搜索结果值对象。

    一个文件在向量库里通常有多条向量（文档分块、图片的 OCR/视觉特征、视频关键帧），
    这里表示的是**其中一条向量的命中**，命中位置字段（页/行号、关键帧起止时间）就是
    那条向量自己的位置。所以同一个 `file_id` 可以出现在多条结果里——一份文档三处提到
    查询词就是三条结果，前端据此给出三个可跳转的位置。
    """

    file_id: str
    file_name: str
    file_type: FileType
    score: float
    snippet: str = ""
    page_number: int | None = None
    line_number: int | None = None
    start_time: float | None = None
    end_time: float | None = None


@dataclass
class SearchFileMetadata:
    path: str
    size: int | None
    modified: str | None
    accessible: bool
