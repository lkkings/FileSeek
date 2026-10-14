"""生成 slim-backend-dependencies 的对照基准。

只能在旧依赖（torch、transformers、imagehash 还在）下运行，结果写入
`tests/fixtures/parity/`。新实现的测试只读这些文件，不再需要旧依赖。

    uv run python scripts/make_parity_fixtures.py

模型目录取 `~/.cache/fileseek/models`；只有 `model_quantized.onnx` 也在时才生成图片向量基准。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from tests.parity_samples import (  # noqa: E402
    EMBEDDING_IMAGE_SIZES,
    PREPROCESS_CASES,
    phash_frames,
    sample_image,
    sample_texts,
)

MODEL_DIR = Path.home() / ".cache" / "fileseek" / "models"
TOKENIZER_DIR = MODEL_DIR / "tokenizer"
OUT = ROOT / "tests" / "fixtures" / "parity"


def make_preprocess() -> None:
    from transformers import AutoImageProcessor

    processor = AutoImageProcessor.from_pretrained(str(TOKENIZER_DIR), trust_remote_code=True)
    arrays: dict[str, np.ndarray] = {}
    for name, (width, height, mode, size) in PREPROCESS_CASES.items():
        image = sample_image(width, height, mode).convert("RGB")
        pixel_values = processor([image], return_tensors="np", size=size)["pixel_values"]
        arrays[name] = pixel_values.detach().cpu().numpy().astype(np.float16)
    np.savez_compressed(OUT / "image_preprocess.npz", **arrays)


def make_token_ids() -> None:
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(str(TOKENIZER_DIR), trust_remote_code=True)
    texts = sample_texts()
    ids = tokenizer(
        texts,
        padding=False,
        truncation=True,
        max_length=tokenizer.model_max_length,
    )["input_ids"]
    records = [{"text": text, "input_ids": list(row)} for text, row in zip(texts, ids, strict=True)]
    (OUT / "token_ids.json").write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")


def make_phash() -> None:
    import imagehash

    records = {
        name: imagehash.phash(frame).hash.flatten().astype(int).tolist()
        for name, frame in phash_frames().items()
    }
    (OUT / "phash.json").write_text(json.dumps(records), encoding="utf-8")


def make_image_embeddings() -> None:
    if not (MODEL_DIR / "model_quantized.onnx").exists():
        print("model not cached, skipping image_embeddings.npz")
        return
    from io import BytesIO

    from fileseek.infrastructure.embedding.jina_clip_v2 import JinaClipV2Embedding

    embedding = JinaClipV2Embedding(cache_dir=MODEL_DIR)
    images: list[bytes] = []
    for width, height, mode in EMBEDDING_IMAGE_SIZES:
        buffer = BytesIO()
        sample_image(width, height, mode).save(buffer, format="PNG")
        images.append(buffer.getvalue())
    vectors = np.asarray(embedding.embed_image(images), dtype=np.float32)
    np.savez_compressed(OUT / "image_embeddings.npz", vectors=vectors)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    make_preprocess()
    make_token_ids()
    make_phash()
    make_image_embeddings()
    for path in sorted(OUT.iterdir()):
        print(f"{path.stat().st_size:>10}  {path.name}")


if __name__ == "__main__":
    Image.init()
    main()
