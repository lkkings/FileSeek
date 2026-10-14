"""真实模型下，图片向量与旧实现（远程预处理 + torchvision）的对照。

基准 `image_embeddings.npz` 由 `scripts/make_parity_fixtures.py` 在旧依赖下生成。
"""

from __future__ import annotations

import socket
from io import BytesIO
from pathlib import Path

import numpy as np
import pytest
from tests.parity_samples import EMBEDDING_IMAGE_SIZES, sample_image

from fileseek.infrastructure.embedding.jina_clip_v2 import JinaClipV2Embedding

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "parity"
MODEL_CACHE = Path.home() / ".cache" / "fileseek" / "models"

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(
        not (MODEL_CACHE / "model_quantized.onnx").exists(),
        reason="需要本地已缓存的 jina-clip-v2 模型",
    ),
]


def _png(width: int, height: int, mode: str) -> bytes:
    buffer = BytesIO()
    sample_image(width, height, mode).save(buffer, format="PNG")
    return buffer.getvalue()


def test_image_vectors_match_previous_implementation(monkeypatch: pytest.MonkeyPatch) -> None:
    # 离线：模型已在本地，加载和推理都不能碰网络。
    def no_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("图片向量化不应访问网络")

    monkeypatch.setattr(socket.socket, "connect", no_network)
    expected = np.load(FIXTURES / "image_embeddings.npz")["vectors"]
    embedding = JinaClipV2Embedding(cache_dir=MODEL_CACHE)

    actual = np.asarray(
        embedding.embed_image([_png(*case) for case in EMBEDDING_IMAGE_SIZES]),
        dtype=np.float32,
    )

    assert actual.shape == expected.shape == (len(EMBEDDING_IMAGE_SIZES), 1024)
    np.testing.assert_allclose(np.linalg.norm(actual, axis=1), 1.0, atol=1e-3)
    cosine = (actual * expected).sum(axis=1)
    assert cosine.min() >= 0.999, cosine
