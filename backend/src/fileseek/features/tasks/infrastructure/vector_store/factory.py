from __future__ import annotations

from pathlib import Path
from functools import lru_cache

from fileseek.config.settings import get_settings

from fileseek.features.tasks.domain.ports import VectorIndexPort
from fileseek.features.tasks.infrastructure.vector_store.chroma_store import (
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
        persist_directory=vector_db_path
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
            )

        raise ValueError(
            f"不支持的 Vector Store provider: {provider}"
        )