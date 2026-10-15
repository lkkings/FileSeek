"""Search feature HTTP 依赖解析。

每个协作者单独开一个 provider，而不是直接 resolve 组合根里装好的 use case：测试要靠
`dependency_overrides` 把 embedder 和向量库换成假实现（真货会下载 jina-clip-v2 权重、
开一个 Chroma 客户端），只有 provider 是可覆盖的单位。
"""

from __future__ import annotations

from fastapi import Request

from fileseek.features.search.application.use_cases import (
    EnhancedSearchUseCase,
    SearchFilesUseCase,
)
from fileseek.features.search.infrastructure.query_worker import QueryEmbeddingClient
from fileseek.shared.application.dependencies import resolve_dependency


def get_search_files_use_case(request: Request) -> SearchFilesUseCase:
    return resolve_dependency(request, "search_files_use_case")


def get_enhanced_search_use_case(request: Request) -> EnhancedSearchUseCase:
    return resolve_dependency(request, "enhanced_search_use_case")


def get_query_embedding_client(request: Request) -> QueryEmbeddingClient:
    return resolve_dependency(request, "query_embedding_client")
