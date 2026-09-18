"""Tests the real encoders against the real weights.

Marked slow and skipped when weights are absent: these load Chinese-CLIP and
multilingual-e5 from disk. Mocking them would verify nothing — the point is that
the actual models place matching text and images near each other.
"""

from __future__ import annotations

import io
from collections.abc import Iterator
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont

from fileseek.models.hardware import HardwareProfile
from fileseek.models.tiers import CPU_BUNDLE, ModelSelection
from fileseek.models.vectors import cosine_similarity, is_normalized
from fileseek.models.weights import WeightStore

pytestmark = pytest.mark.slow

CPU_ONLY = HardwareProfile()

SELECTION = ModelSelection(tier="cpu", device="cpu", reason="test", profile=CPU_ONLY)

_CANDIDATE_DIRS = (
    Path("D:/FileSeek/.models"),
    Path(__file__).resolve().parents[2] / ".models",
)

_FONT_CANDIDATES = (
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
)


def _weight_store() -> WeightStore | None:
    for candidate in _CANDIDATE_DIRS:
        store = WeightStore(candidate)
        if store.readiness(CPU_BUNDLE).is_ready:
            return store
    return None


def _png(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="PNG")
    return buffer.getvalue()


def solid(colour: tuple[int, int, int], size: int = 224) -> bytes:
    return _png(Image.new("RGB", (size, size), colour))


def rendered_text(text: str, size: tuple[int, int] = (460, 130)) -> bytes:
    image = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(image)
    for candidate in _FONT_CANDIDATES:
        try:
            draw.text((20, 30), text, fill="black", font=ImageFont.truetype(candidate, 52))
            return _png(image)
        except OSError:
            continue
    pytest.skip("no CJK font available to render an OCR fixture")


@pytest.fixture(scope="module")
def encoders() -> Iterator[object]:
    store = _weight_store()
    if store is None:
        pytest.skip("CPU-tier model weights are not present")

    from fileseek.models.encoders import LocalEncoders

    yield LocalEncoders(SELECTION, store)


def test_image_vectors_have_the_declared_width(encoders) -> None:  # type: ignore[no-untyped-def]
    vectors = encoders.encode_images([solid((220, 30, 30))])

    assert len(vectors) == 1
    assert len(vectors[0]) == CPU_BUNDLE.image_dimensions


def test_image_vectors_are_normalized(encoders) -> None:  # type: ignore[no-untyped-def]
    vectors = encoders.encode_images([solid((220, 30, 30)), solid((30, 30, 220))])

    assert all(is_normalized(vector) for vector in vectors)


def test_a_batch_encodes_every_image(encoders) -> None:  # type: ignore[no-untyped-def]
    vectors = encoders.encode_images(
        [solid((220, 30, 30)), solid((30, 220, 30)), solid((30, 30, 220))]
    )

    assert len(vectors) == 3


def test_batching_matches_encoding_one_at_a_time(encoders) -> None:  # type: ignore[no-untyped-def]
    """Batching is a throughput optimisation, so it must not change the vectors."""
    images = [solid((220, 30, 30)), solid((30, 30, 220))]

    batched = encoders.encode_images(images)
    separately = [encoders.encode_images([image])[0] for image in images]

    for left, right in zip(batched, separately, strict=True):
        assert cosine_similarity(left, right) == pytest.approx(1.0, abs=1e-4)


def test_empty_image_batch_returns_nothing(encoders) -> None:  # type: ignore[no-untyped-def]
    assert encoders.encode_images([]) == []


def test_chinese_query_matches_the_right_image(encoders) -> None:  # type: ignore[no-untyped-def]
    """The product's queries are Chinese, so the shared space must be Chinese-aligned."""
    red, blue = encoders.encode_images([solid((225, 25, 25)), solid((25, 25, 225))])
    red_query = encoders.encode_query("一张红色的图片")
    blue_query = encoders.encode_query("一张蓝色的图片")

    assert cosine_similarity(red_query, red) > cosine_similarity(red_query, blue)
    assert cosine_similarity(blue_query, blue) > cosine_similarity(blue_query, red)


def test_query_vectors_share_the_image_space(encoders) -> None:  # type: ignore[no-untyped-def]
    query = encoders.encode_query("一张图片")

    assert len(query) == CPU_BUNDLE.image_dimensions
    assert is_normalized(query)


def test_english_query_also_works(encoders) -> None:  # type: ignore[no-untyped-def]
    """Chinese alignment must not have cost the English ability."""
    red, blue = encoders.encode_images([solid((225, 25, 25)), solid((25, 25, 225))])
    query = encoders.encode_query("a red picture")

    assert cosine_similarity(query, red) > cosine_similarity(query, blue)


def test_passage_vectors_have_the_declared_width(encoders) -> None:  # type: ignore[no-untyped-def]
    vectors = encoders.encode_texts(["深度学习的论文综述"])

    assert len(vectors[0]) == CPU_BUNDLE.text_dimensions
    assert is_normalized(vectors[0])


def test_empty_text_batch_returns_nothing(encoders) -> None:  # type: ignore[no-untyped-def]
    assert encoders.encode_texts([]) == []


def test_document_query_ranks_the_matching_passage_first(encoders) -> None:  # type: ignore[no-untyped-def]
    passages = encoders.encode_texts(
        ["一篇关于深度学习与神经网络的论文", "今天的天气预报和气温变化"]
    )
    query = encoders.encode_text_query("深度学习的论文")

    assert cosine_similarity(query, passages[0]) > cosine_similarity(query, passages[1])


def test_cross_lingual_meaning_outranks_unrelated_text(encoders) -> None:  # type: ignore[no-untyped-def]
    """A Chinese query has to reach an English document about the same subject."""
    passages = encoders.encode_texts(
        ["a survey of deep learning and neural networks", "a recipe for tomato soup"]
    )
    query = encoders.encode_text_query("深度学习的论文")

    assert cosine_similarity(query, passages[0]) > cosine_similarity(query, passages[1])


def test_document_and_image_spaces_are_separate(encoders) -> None:  # type: ignore[no-untyped-def]
    visual = encoders.encode_query("一张红色的图片")
    textual = encoders.encode_text_query("一张红色的图片")

    assert len(visual) != len(textual)


def test_chinese_text_in_an_image_is_recognised(encoders) -> None:  # type: ignore[no-untyped-def]
    recognised = encoders.recognize_text(rendered_text("深度学习"))

    assert "深度学习" in recognised


def test_recognised_text_makes_a_screenshot_findable(encoders) -> None:  # type: ignore[no-untyped-def]
    """This is what lets a screenshot be found by the words shown in it."""
    recognised = encoders.recognize_text(rendered_text("机器学习笔记"))

    assert any(term in recognised for term in ("机器", "学习", "笔记"))


def test_image_without_text_recognises_nothing(encoders) -> None:  # type: ignore[no-untyped-def]
    assert encoders.recognize_text(solid((120, 120, 120))).strip() == ""


def test_describe_reports_the_loaded_models(encoders) -> None:  # type: ignore[no-untyped-def]
    image_model, text_model, image_dimensions, text_dimensions = encoders.describe()

    assert "chinese-clip" in image_model
    assert "multilingual" in text_model
    assert image_dimensions == CPU_BUNDLE.image_dimensions
    assert text_dimensions == CPU_BUNDLE.text_dimensions


def test_missing_weights_are_reported_clearly(tmp_path: Path) -> None:
    from fileseek.models.encoders import LocalEncoders, WeightsMissingError

    with pytest.raises(WeightsMissingError, match="are not present") as excinfo:
        LocalEncoders(SELECTION, WeightStore(tmp_path / "nowhere"))

    assert excinfo.value.repo_id == CPU_BUNDLE.image.repo_id
