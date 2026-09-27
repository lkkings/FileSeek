from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from fileseek.config.settings import get_settings
from fileseek.infrastructure.vector_store.base import (
    VectorIndexPort,
    DistanceMetric
)
from fileseek.infrastructure.vector_store.chroma_store import (
    ChromaVectorStore,
)


@lru_cache
def get_vector_store() -> VectorIndexPort:
    """进程内共享的向量存储。"""
    settings = get_settings()
    vector_db_path = settings.vector_db_path
    if vector_db_path is None:  # pragma: no cover - Settings.__init__ 已派生
        msg = "vector_db_path 未配置"
        raise RuntimeError(msg)
    return VectorStoreFactory.create(
        provider=settings.vector_store_provider,
        persist_directory=vector_db_path,
        distance_metric=settings.vector_distance_metric
    )

class VectorStoreFactory:
    """向量存储实现工厂。"""

    _DEFAULT_PROVIDER = "chroma"

    @classmethod
    def create(
        cls,
        provider: str = _DEFAULT_PROVIDER,
        *,
        persist_directory: Path,
        distance_metric: str,
    ) -> VectorIndexPort:
        """创建向量存储实例。

        Args:
            provider: 向量数据库类型。
            persist_directory: 向量数据库持久化目录。

        Returns:
            VectorIndexPort: 向量存储抽象。

        Raises:
            ValueError: 不支持的向量存储类型。
        """
        normalized_provider = provider.strip().lower()

        if normalized_provider == "chroma":
            return ChromaVectorStore(
                persist_directory=persist_directory,
                distance_metric=DistanceMetric(distance_metric),
            )

        raise ValueError(
            f"不支持的 Vector Store provider: {provider}"
        )
