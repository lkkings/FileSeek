"""The desktop app pre-downloads the model into `embedding_model_cache_dir`.

`release/runtime.json` → `model.files` lists them under these relative paths, and the Rust
side writes each one there. If `ensure_model_cached` looked anywhere else, every user would
download the 874MB model a second time from Hugging Face on first use.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fileseek.shared.utils import model_cache

RUNTIME_CONFIG = Path(__file__).resolve().parents[3] / "release" / "runtime.json"
PREDOWNLOADED = tuple(
    f["path"] for f in json.loads(RUNTIME_CONFIG.read_text(encoding="utf-8"))["model"]["files"]
)


def test_predownloaded_files_are_used_without_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in PREDOWNLOADED:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")

    def no_network(*args: object, **kwargs: object) -> str:
        raise AssertionError(f"tried to download {args}")

    monkeypatch.setattr("huggingface_hub.hf_hub_download", no_network)

    onnx_path, tokenizer_dir = model_cache.ensure_model_cached("jinaai/jina-clip-v2", tmp_path)

    assert onnx_path == tmp_path / "model_quantized.onnx"
    assert tokenizer_dir == tmp_path / "tokenizer"
