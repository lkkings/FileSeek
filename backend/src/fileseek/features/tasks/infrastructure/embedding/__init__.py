from fileseek.features.tasks.infrastructure.embedding.factory import EmbeddingFactory,get_embedding_service
from fileseek.features.tasks.infrastructure.embedding.jina_clip_v2 import JinaClipV2Embedding

__all__ = [
    "EmbeddingFactory",
    "JinaClipV2Embedding",
    "get_embedding_service"
]