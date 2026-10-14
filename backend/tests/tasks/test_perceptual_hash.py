"""感知哈希与旧实现（`imagehash.phash`）的对照。

基准由 `scripts/make_parity_fixtures.py` 在旧依赖下生成；帧在这里按同一份逻辑重新画出来。
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from tests.parity_samples import phash_frames

from fileseek.features.tasks.infrastructure.file_processor.perceptual_hash import (
    PerceptualHash,
    phash,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "parity"
EXPECTED = json.loads((FIXTURES / "phash.json").read_text(encoding="utf-8"))
FRAMES = phash_frames()


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_matches_previous_implementation(name: str) -> None:
    expected = PerceptualHash(np.asarray(EXPECTED[name], dtype=bool))

    assert phash(FRAMES[name]) - expected <= 2


def test_identical_frames_have_zero_distance() -> None:
    assert phash(FRAMES["base"]) - phash(FRAMES["base"].copy()) == 0


def test_similar_frames_are_closer_than_different_ones() -> None:
    base = phash(FRAMES["base"])

    assert base - phash(FRAMES["noisy"]) < base - phash(FRAMES["other"])


def test_hash_is_64_bits() -> None:
    assert phash(FRAMES["small"]).bits.shape == (64,)


def test_mismatched_lengths_are_rejected() -> None:
    with pytest.raises(TypeError):
        _ = PerceptualHash(np.zeros(64, dtype=bool)) - PerceptualHash(np.zeros(16, dtype=bool))
