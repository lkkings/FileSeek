

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from fileseek.shared.domain.file_types import FileType


@dataclass(frozen=True)
class IndexedFileMetadata:
    """索引时随每条向量一起落盘的文件元信息。

    检索要按文件名/体积/修改时间筛选，而这些属性在向量库里查不到——除非索引时就写进去。
    写进去之后检索不必再回库表取一遍，一次 query 就能拿到渲染结果所需的全部字段。

    `modified_ts` 是 `modified` 的 epoch 秒副本：向量库的范围比较是数值比较，ISO 字符串
    比不出大小。两个字段都留着，前者给筛选用，后者直接回给前端。
    """

    file_id: str
    file_name: str
    path: str
    size: int | None
    modified: str | None
    modified_ts: float | None
    accessible: bool


@dataclass(frozen=True)
class VectorHit:
    """向量库的一条命中，元信息全部来自向量元数据。

    一条命中可能是单个片段，也可能是若干**连续**片段合并后的一段（见
    `ChromaVectorStore._merge_adjacent`）。合并后位置字段取这一段的起点，
    `snippet` 是按顺序拼接的正文，`score` 取段内最高分。

    `chunk_index` / `chunk_end_index` 描述文档片段在全文里占据的区间（闭区间，
    单片段时两者相等），供合并时判断相邻用。视频靠 `start_time` / `end_time`
    在时间轴上判断相邻，不用这两个字段；图片的 OCR 与视觉特征之间没有顺序关系，
    不参与合并。
    """

    file_id: str
    file_name: str
    file_type: FileType
    score: float
    path: str
    size: int | None
    modified: str | None
    accessible: bool
    snippet: str = ""
    page_number: int | None = None
    line_number: int | None = None
    start_time: float | None = None
    end_time: float | None = None
    chunk_index: int | None = None
    chunk_end_index: int | None = None


@dataclass(frozen=True)
class VectorSearchFilters:
    """检索侧的高级筛选条件，下推到向量库执行。"""

    name_query: str | None = None
    min_size: float | None = None
    max_size: float | None = None
    start_date: str | None = None
    end_date: str | None = None

class VectorIndexPort(Protocol):
    def add_document_vectors(
        self,
        metadata: IndexedFileMetadata,
        chunks: list[dict[str, object]],
    ) -> None: ...

    def add_image_vectors(
        self,
        metadata: IndexedFileMetadata,
        features: list[dict[str, object]],
    ) -> None: ...

    def add_video_vectors(
        self,
        metadata: IndexedFileMetadata,
        keyframes: list[dict[str, object]],
    ) -> None: ...

    def search(
        self,
        query_vector: list[float],
        file_types: list[FileType],
        limit: int,
        filters: VectorSearchFilters | None = None,
    ) -> list[VectorHit]: ...

    def delete_file_vectors(self, file_id: str) -> None: ...
