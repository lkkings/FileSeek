from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pytest

from fileseek.infrastructure.embedding.jina_clip_v2 import JinaClipV2Embedding
from fileseek.shared.domain.exceptions import InferenceError
from fileseek.shared.utils import model_cache
from fileseek.shared.utils.model_cache import ensure_text_model, text_model_path

MODEL_CACHE = Path.home() / ".cache" / "fileseek" / "models"
JOINT_MODEL = MODEL_CACHE / "model_quantized.onnx"
needs_model = pytest.mark.skipif(
    not JOINT_MODEL.exists(), reason="需要本地已缓存的 jina-clip-v2 模型"
)


def test_text_model_path_sits_next_to_joint_model() -> None:
    assert text_model_path(Path("/m/model_quantized.onnx")) == Path("/m/model_quantized.text.onnx")


def test_existing_text_model_is_reused(tmp_path: Path) -> None:
    joint = tmp_path / "model_quantized.onnx"
    target = text_model_path(joint)
    target.write_bytes(b"already there")

    assert ensure_text_model(joint) == target
    assert target.read_bytes() == b"already there"


def test_extraction_failure_returns_none_and_leaves_no_partial_file(tmp_path: Path, caplog) -> None:
    joint = tmp_path / "model_quantized.onnx"
    joint.write_bytes(b"not an onnx model")

    with caplog.at_level(logging.WARNING):
        assert ensure_text_model(joint) is None

    assert not text_model_path(joint).exists()
    assert not text_model_path(joint).with_suffix(".onnx.tmp").exists()
    assert "文本塔子图生成失败" in caplog.text


def test_text_only_falls_back_to_joint_model_when_subgraph_unavailable(monkeypatch) -> None:
    embedding = JinaClipV2Embedding(text_only=True)
    monkeypatch.setattr(
        "fileseek.infrastructure.embedding.jina_clip_v2.ensure_text_model",
        lambda onnx_path: None,
    )

    assert embedding._load_text_session(Path("/unused.onnx"), object()) is None  # type: ignore[arg-type]


def test_text_only_rejects_image_embedding() -> None:
    with pytest.raises(InferenceError, match="text_only"):
        JinaClipV2Embedding(text_only=True).embed_image(b"img")


@pytest.mark.slow
@needs_model
def test_text_tower_subgraph_matches_joint_model(tmp_path: Path, monkeypatch) -> None:
    # 在临时目录里生成子图，不动用户缓存目录里的那份。
    joint_link = tmp_path / "model_quantized.onnx"
    joint_link.symlink_to(JOINT_MODEL)
    tokenizer_link = tmp_path / "tokenizer"
    tokenizer_link.symlink_to(MODEL_CACHE / "tokenizer")
    monkeypatch.setattr(
        model_cache,
        "ensure_model_cached",
        lambda model_name, cache_dir: (joint_link, tokenizer_link),
    )
    monkeypatch.setattr(
        "fileseek.infrastructure.embedding.jina_clip_v2.ensure_model_cached",
        lambda model_name, cache_dir: (joint_link, tokenizer_link),
    )

    text = JinaClipV2Embedding(cache_dir=tmp_path, text_only=True)
    joint = JinaClipV2Embedding(cache_dir=tmp_path)
    session, _, image_processor = text._ensure_loaded()

    assert [i.name for i in session.get_inputs()] == ["input_ids"]
    assert image_processor is None
    assert text_model_path(joint_link).exists()

    queries = [
        "上个月的旅游照片", "Q2 财务报告", "how to parse pdf cross reference table", "猫",
        "sunset on the beach", "会议纪要 2026", "invoice", "PDF 字体嵌入规范",
        "ONNX runtime memory", "机器学习论文", "birthday party video", "合同扫描件",
        "resume", "北京 天气", "annotation dictionary", "xref stream", "color space ICC",
        "数字签名", "encryption dictionary", "page tree",
    ]
    a = np.asarray(text.embed_text(queries, query=True))
    b = np.asarray(joint.embed_text(queries, query=True))
    cosine = (a * b).sum(axis=1) / np.linalg.norm(a, axis=1) / np.linalg.norm(b, axis=1)

    assert a.shape == (20, 1024)
    assert cosine.min() >= 0.9999
