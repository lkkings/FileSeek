"""语义搜索用例。

编排搜索流程：查询文本向量化 -> 带筛选条件在向量库中检索 -> 按媒体类型分组截断。

三点值得说明：

- 元信息（路径、体积、修改时间、可访问性）取自向量元数据，不回库表。索引时这些字段就
  随每条向量一起落盘了，检索因此只需一次向量库往返。
- 高级筛选（文件名/体积/日期）一并下推到向量库执行，否则"先取 Top N 再筛"会把结果筛空。
- `limit` 对每种媒体类型独立生效。三种类型都搜时最多返回 3 * limit 条，所以截断必须
  在分组之后做，不能在合并列表上做。
- 嵌入模型（jina-clip-v2）未接入时 `embed_text` 会抛 NotImplementedError。这里捕获它
  并返回空结果，让 API 契约在底层模型接入前也能正常响应。
"""

from __future__ import annotations

import logging
from typing import cast

from fileseek.features.search.application.dto import SearchFileMetadata as SearchFileMetadataView
from fileseek.features.search.application.queries import SearchFilesQuery
from fileseek.features.search.domain.entities import SearchResult
from fileseek.features.tasks.domain.ports import (
    EmbeddingPort,
    VectorHit,
    VectorIndexPort,
    VectorSearchFilters,
)
from fileseek.shared.domain.file_types import FileType

logger = logging.getLogger(__name__)

_DEFAULT_FILE_TYPES = [FileType.DOCUMENT, FileType.IMAGE, FileType.VIDEO]
_BYTES_PER_MB = 1024 * 1024

SearchHit = tuple[SearchResult, SearchFileMetadataView | None]


class SearchFilesUseCase:
    def __init__(
        self,
        embedder: EmbeddingPort,
        vector_store: VectorIndexPort,
    ) -> None:
        self.embedder = embedder
        self.vector_store = vector_store

    async def execute(self, request: SearchFilesQuery) -> list[SearchHit]:
        """执行语义搜索。

        Args:
            request: 查询文本、媒体类型、每类 Top N 及高级筛选条件

        Returns:
            `(SearchResult, 文件元数据)` 列表，每种媒体类型各自按得分降序、最多
            `request.limit` 条。一条结果是一个命中片段，所以同一个文件命中多处时会
            出现多条。底层嵌入模型未接入时返回空列表。
        """
        # file_types 为 None 表示"未限定"，空列表表示"限定为空集"——后者没有可搜的
        # 类型，直接返回，不要退化成搜全部。
        if request.file_types is not None and not request.file_types:
            return []
        types = _DEFAULT_FILE_TYPES if not isinstance(request.file_types,list) or len(request.file_types) == 0 else request.file_types

        hits = await self._search_vectors(request, types)
        if not hits:
            return []

        return self._group_and_cap(hits, types, request.limit)

    async def _search_vectors(
        self,
        request: SearchFilesQuery,
        types: list[FileType],
    ) -> list[VectorHit]:
        """向量检索。嵌入模型未接入或检索失败时返回空列表。"""
        try:
            # `embed_text` 永远返回一批（传单条字符串也是 `[[...]]`），而向量库要的是单条
            # 向量：`search` 内部会把它包成 `query_embeddings=[query_vector]`。所以这里取第 0
            # 条，不取就多一层，Chroma 报 "Expected embeddings to be ... got [[["。
            #
            # 原来这里是 `cast("list[float]", ...)`：cast 只改静态类型、不动运行期的值，
            # 所以它把这个形状错误藏住了，反而更难查。
            batch = self.embedder.embed_text(request.query, query=True)
            query_vector = cast("list[list[float]]", batch)[0]

            return self.vector_store.search(
                query_vector,
                types,
                request.limit,
                _to_filters(request),
            )
        except NotImplementedError:
            logger.warning("嵌入模型未接入，搜索返回空结果")
            return []
        except Exception:
            # 检索失败不该把整个请求打成 500：前端拿到空结果仍能正常渲染。
            logger.exception("向量检索失败，搜索返回空结果")
            return []

    @staticmethod
    def _group_and_cap(
        hits: list[VectorHit],
        types: list[FileType],
        limit: int,
    ) -> list[SearchHit]:
        """按媒体类型分别排序并截断到 limit。"""
        grouped: dict[FileType, list[SearchHit]] = {file_type: [] for file_type in types}

        for hit in hits:
            bucket = grouped.get(hit.file_type)
            if bucket is None:
                continue
            bucket.append((_to_result(hit), _to_metadata(hit)))

        results: list[SearchHit] = []
        for file_type in types:
            bucket = grouped[file_type]
            bucket.sort(key=lambda item: item[0].score, reverse=True)
            results.extend(bucket[:limit])
        return results


def _to_filters(request: SearchFilesQuery) -> VectorSearchFilters:
    """把查询里的高级筛选条件转成下推给向量库的条件。"""
    return VectorSearchFilters(
        name_query=request.name_query,
        min_size=request.min_size_m * _BYTES_PER_MB if request.min_size_m is not None else None,
        max_size=request.max_size_m * _BYTES_PER_MB if request.max_size_m is not None else None,
        start_date=request.start_date,
        end_date=request.end_date,
    )


def _to_result(hit: VectorHit) -> SearchResult:
    return SearchResult(
        file_id=hit.file_id,
        file_name=hit.file_name,
        file_type=hit.file_type,
        score=hit.score,
        snippet=hit.snippet,
        page_number=hit.page_number,
        line_number=hit.line_number,
        start_time=hit.start_time,
        end_time=hit.end_time,
    )


def _to_metadata(hit: VectorHit) -> SearchFileMetadataView:
    return SearchFileMetadataView(
        path=hit.path,
        size=hit.size,
        modified=hit.modified,
        accessible=hit.accessible,
    )
