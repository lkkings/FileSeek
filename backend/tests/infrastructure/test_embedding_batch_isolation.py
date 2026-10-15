from __future__ import annotations

from io import BytesIO
from pathlib import Path

import numpy as np
import pytest
from tests.parity_samples import sample_image

from fileseek.infrastructure.embedding.jina_clip_v2 import JinaClipV2Embedding

MODEL_CACHE = Path.home() / ".cache" / "fileseek" / "models"

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(
        not (MODEL_CACHE / "model_quantized.onnx").exists(),
        reason="需要本地已缓存的 jina-clip-v2 模型",
    ),
]


def test_real_text_embeddings_are_invariant_to_batch_composition() -> None:
    embedding = JinaClipV2Embedding(cache_dir=MODEL_CACHE)
    texts = ["天空", "a long document chunk about embedding batch isolation"]

    isolated = [np.asarray(embedding.embed_text([text]), dtype=np.float32)[0] for text in texts]
    batched = np.asarray(embedding.embed_text(texts), dtype=np.float32)

    np.testing.assert_allclose(batched, isolated, atol=1e-6)


def test_real_image_embeddings_are_invariant_to_batch_composition() -> None:
    embedding = JinaClipV2Embedding(cache_dir=MODEL_CACHE)
    images = []
    for size, seed in [((64, 48), 1), ((48, 64), 2)]:
        buffer = BytesIO()
        sample_image(*size, "RGB", seed=seed).save(buffer, format="PNG")
        images.append(buffer.getvalue())

    isolated = [np.asarray(embedding.embed_image([image]), dtype=np.float32)[0] for image in images]
    batched = np.asarray(embedding.embed_image(images), dtype=np.float32)

    np.testing.assert_allclose(batched, isolated, atol=1e-6)
