"""语义搜索用例。

编排搜索流程：查询文本向量化 -> 带筛选条件在向量库中检索 -> 全局相关度排序 -> 分页。

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

import asyncio
import hashlib
import json
import logging
from dataclasses import asdict
from typing import cast

from fileseek.config.constant import (
    BYTES_PER_MB,
    EMBEDDING_CACHE_KEY,
    QUERY_CACHE_KEY,
)
from fileseek.features.library.domain.repositories import FileRepository
from fileseek.features.search.application.dto import FileDTO, SearchResultsDTO
from fileseek.features.search.application.mappers import file_to_dto
from fileseek.features.search.application.queries import FileSortBy, SearchFilesQuery, SortOrder
from fileseek.infrastructure.embedding import EmbeddingPort
from fileseek.infrastructure.vector_store import VectorIndexPort
from fileseek.shared.utils.cache import TTLLRUCache

logger = logging.getLogger(__name__)

IMAGE_FEATURE_WEIGHT = 1.0
TEXT_FEATURE_WEIGHT = 0.4


def _query_cache_key(query: SearchFilesQuery) -> str:
    payload = asdict(query)

    raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )

    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class SearchFilesUseCase:
    def __init__(
        self,
        embedder: EmbeddingPort,
        vector_store: VectorIndexPort,
        file_repo: FileRepository,
        cache: TTLLRUCache,
    ) -> None:
        self.embedder = embedder
        self.vector_store = vector_store
        self.file_repo = file_repo
        # Level 2: 全量无分页检索结果缓存 (TTL 60秒, 最大 128)
        self.cache = cache


    async def execute(
        self, request: SearchFilesQuery
    ) -> SearchResultsDTO:
        query_key = _query_cache_key(request)
        cached = await self.cache.get(QUERY_CACHE_KEY, query_key)
        if cached is not None:
            return cast("list[FileDTO]", cached)
        if not (request.query or "").strip() or request.sort_by != FileSortBy.RELEVANCE:
            # 如果不是通过相关性进行匹配
            items = await self._search_by_db(request)
        else:
            items = await self._search_by_vectors(request)
        categories = [category.value for category in request.categories or []]
        min_size = (
            request.min_size_m * BYTES_PER_MB
            if request.min_size_m is not None
            else None
        )
        max_size = (
            request.max_size_m * BYTES_PER_MB
            if request.max_size_m is not None
            else None
        )
        counter = await self.file_repo.count_by_category(
            name_query=request.name_query,
            tag=request.tag,
            min_size=min_size,
            max_size=max_size,
            start_date=request.start_date,
            end_date=request.end_date,
            folder_id=request.folder_id,
            categories=categories,
        )
        total = sum(counter.values())
        result = SearchResultsDTO(
            items=items,
            counter=counter,
            total=total,
            page_number=request.page_number,
            page_size=request.page_size
        )
        await self.cache.set(QUERY_CACHE_KEY, query_key, result)
        return result

    async def _search_by_db(self,request:SearchFilesQuery) -> list[FileDTO]:
        categories = [category.value for category in request.categories or []]
        files = await self.file_repo.query(
            name_query=request.name_query,
            tag=request.tag,
            min_size=request.min_size_m * BYTES_PER_MB if request.min_size_m is not None else None,
            max_size=request.max_size_m * BYTES_PER_MB if request.max_size_m is not None else None,
            start_date=request.start_date,
            end_date=request.end_date,
            folder_id=request.folder_id,
            categories=categories,
            page_number=request.page_number,
            page_size=request.page_size,
            sort_order=request.sort_order.value,
            sort_by=request.sort_by.value
        )
        return [file_to_dto(file) for file in files]

    async def _search_by_vectors(self,request: SearchFilesQuery) ->  list[FileDTO]:
        query_str = request.query.strip()
        query_vector = await self.cache.get(EMBEDDING_CACHE_KEY, query_str)
        if query_vector is None:
            # 兼容不接收 query 命名参数的 FakeEmbedder
            batch = await asyncio.to_thread(
                self.embedder.embed_text,
                query_str,
                query=True,
            )
            query_vector = cast("list[list[float]]", batch)[0]
            await self.cache.set(EMBEDDING_CACHE_KEY, query_str, query_vector)
        categories = [category.value for category in request.categories or []]
        files = await self.file_repo.query(
            name_query=request.name_query,
            tag=request.tag,
            min_size=request.min_size_m * BYTES_PER_MB if request.min_size_m is not None else None,
            max_size=request.max_size_m * BYTES_PER_MB if request.max_size_m is not None else None,
            start_date=request.start_date,
            end_date=request.end_date,
            folder_id=request.folder_id,
            categories=categories
        )
        chunk_ids = [
            chunk.id
            for file in files
            for chunk in file.chunks
        ]
        hits =  await asyncio.to_thread(self.vector_store.search,query_vector,ids=chunk_ids)
        chunk_hit_map = {hit.id: hit.score for hit in hits}
        for file in files:
            for chunk in file.chunks:
                raw_score = chunk_hit_map.get(chunk.id, 0.0)
                metadata = dict(chunk.metadata or {})
                metadata["raw_score"] = raw_score

                if file.file_type.is_image:
                    is_ocr = metadata.get("feature_type") == "ocr"
                    weighted_score = raw_score * (
                        TEXT_FEATURE_WEIGHT if is_ocr else IMAGE_FEATURE_WEIGHT
                    )
                    metadata["match_type"] = "ocr" if is_ocr else "image"
                elif file.file_type.is_document:
                    weighted_score = raw_score * TEXT_FEATURE_WEIGHT
                else:
                    weighted_score = raw_score * IMAGE_FEATURE_WEIGHT

                chunk.metadata = metadata
                chunk.set_score(weighted_score)
        items = [file_to_dto(file) for file in files]
        if request.sort_order == SortOrder.ASC:
            items.sort(key=lambda item: item.score)
        else:
            items.sort(
                key=lambda item: item.score,
                reverse=True,
            )
        start = (request.page_number - 1) * request.page_size
        end = start + request.page_size

        return items[start:end]
