from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from fileseek.config.settings import get_settings
from fileseek.infrastructure.embedding.base import EmbeddingPort
from fileseek.infrastructure.embedding.jina_clip_v2 import (
    JinaClipV2Embedding,
)


@lru_cache
def get_embedding_service() -> EmbeddingPort:
    """进程内共享的嵌入服务（模型懒加载）。"""
    settings = get_settings()
    return EmbeddingFactory.create(
        provider=settings.embedding_provider,
        model_name=settings.embedding_model_name,
        cache_dir=settings.embedding_model_cache_dir,
        intra_op_num_threads=settings.intra_op_num_threads,
        inter_op_num_threads=settings.inter_op_num_threads,
    )


class EmbeddingFactory:
    """Embedding 实现工厂。

    负责根据配置创建具体的 EmbeddingPort 实现。

    工厂本身不负责：
        - 模型加载
        - 模型缓存
        - ONNX 推理
        - 文本处理
        - 图片处理
        - 向量存储
    """

    _DEFAULT_PROVIDER = "jina-clip-v2"

    @classmethod
    def create(
        cls,
        provider: str = _DEFAULT_PROVIDER,
        *,
        model_name: str | None = None,
        cache_dir: Path | None = None,
        intra_op_num_threads: int | None = None,
        inter_op_num_threads: int | None = None,
        text_only: bool = False,
    ) -> EmbeddingPort:
        """创建 Embedding 实现。

        Args:
            provider:
                Embedding 实现类型。

            model_name:
                模型名称。未指定时使用具体实现的默认模型。

            cache_dir:
                模型缓存目录。

            intra_op_num_threads:
                ONNX Runtime 算子内部线程数。

            inter_op_num_threads:
                ONNX Runtime 算子之间线程数。

            text_only:
                只做文本向量化（查询进程），优先加载文本塔子图。

        Returns:
            EmbeddingPort 实例。

        Raises:
            ValueError:
                不支持的 provider。
        """
        normalized_provider = provider.strip().lower()

        if normalized_provider == "jina-clip-v2":
            return JinaClipV2Embedding(
                model_name=model_name or JinaClipV2Embedding.DEFAULT_MODEL_NAME,
                cache_dir=cache_dir,
                intra_op_num_threads=intra_op_num_threads,
                inter_op_num_threads=inter_op_num_threads,
                text_only=text_only,
            )

        raise ValueError(f"不支持的 Embedding provider: {provider}")
