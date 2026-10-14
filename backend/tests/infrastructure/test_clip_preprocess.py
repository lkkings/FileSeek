"""图片预处理与旧实现（远程 `JinaCLIPImageProcessor` + torchvision）的对照。

基准由 `scripts/make_parity_fixtures.py` 在旧依赖下生成；样本在这里按同一份逻辑重新画出来。
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from tests.parity_samples import PREPROCESS_CASES, sample_image

from fileseek.infrastructure.embedding.clip_preprocess import ClipImagePreprocessor
from fileseek.shared.domain.exceptions import ModelLoadError

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "parity"

# jina-clip-v2 的 preprocessor_config.json（去掉 auto_map），只把 size 换成每个用例的值。
JINA_CONFIG = {
    "fill_color": 0,
    "image_processor_type": "JinaCLIPImageProcessor",
    "interpolation": "bicubic",
    "mean": [0.48145466, 0.4578275, 0.40821073],
    "resize_mode": "shortest",
    "size": 512,
    "std": [0.26862954, 0.26130258, 0.27577711],
}


def _write_config(directory: Path, **overrides: object) -> Path:
    (directory / "preprocessor_config.json").write_text(
        json.dumps({**JINA_CONFIG, **overrides}), encoding="utf-8"
    )
    return directory


@pytest.mark.parametrize("name", sorted(PREPROCESS_CASES))
def test_matches_previous_implementation(name: str, tmp_path: Path) -> None:
    width, height, mode, size = PREPROCESS_CASES[name]
    expected = np.load(FIXTURES / "image_preprocess.npz")[name].astype(np.float32)
    preprocessor = ClipImagePreprocessor.from_dir(_write_config(tmp_path, size=size))

    # 和生产路径一样：`_load_image` 先转 RGB，再交给预处理器。
    actual = preprocessor([sample_image(width, height, mode).convert("RGB")])

    assert actual.dtype == np.float32
    assert actual.shape == expected.shape == (1, 3, size, size)
    assert float(np.abs(actual - expected).max()) < 0.05


def test_batch_is_stacked_in_order(tmp_path: Path) -> None:
    preprocessor = ClipImagePreprocessor.from_dir(_write_config(tmp_path, size=32))
    images = [sample_image(50, 40, "RGB", seed=seed) for seed in range(3)]

    batch = preprocessor(images)

    assert batch.shape == (3, 3, 32, 32)
    for index, image in enumerate(images):
        np.testing.assert_array_equal(batch[index], preprocessor([image])[0])


@pytest.mark.parametrize("mode", ["L", "RGBA", "P"])
def test_non_rgb_input_is_converted(mode: str, tmp_path: Path) -> None:
    preprocessor = ClipImagePreprocessor.from_dir(_write_config(tmp_path, size=32))

    assert preprocessor([sample_image(60, 45, mode)]).shape == (1, 3, 32, 32)


def test_reads_real_model_config(tmp_path: Path) -> None:
    preprocessor = ClipImagePreprocessor.from_dir(_write_config(tmp_path))

    assert preprocessor.size == 512


@pytest.mark.parametrize(
    "overrides",
    [
        {"resize_mode": "longest"},
        {"resize_mode": "squash"},
        {"interpolation": "random"},
        {"size": [512, 384]},
        {"mean": [0.5, 0.5]},
    ],
)
def test_unsupported_config_fails_at_load(overrides: dict[str, object], tmp_path: Path) -> None:
    with pytest.raises(ModelLoadError):
        ClipImagePreprocessor.from_dir(_write_config(tmp_path, **overrides))


def test_missing_config_fails_at_load(tmp_path: Path) -> None:
    with pytest.raises(ModelLoadError):
        ClipImagePreprocessor.from_dir(tmp_path)
