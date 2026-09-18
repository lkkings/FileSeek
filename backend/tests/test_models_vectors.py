import math

import pytest

from fileseek.models.vectors import (
    ZeroVectorError,
    cosine_similarity,
    is_normalized,
    l2_norm,
    mean_vector,
    normalize,
    normalize_all,
)


def test_normalized_vector_has_unit_length() -> None:
    normalized = normalize([3.0, 4.0])

    assert math.isclose(l2_norm(normalized), 1.0)
    assert is_normalized(normalized) is True


def test_normalize_preserves_direction() -> None:
    assert normalize([3.0, 4.0]) == pytest.approx([0.6, 0.8])


def test_already_normalized_vector_is_unchanged() -> None:
    assert normalize([1.0, 0.0, 0.0]) == pytest.approx([1.0, 0.0, 0.0])


def test_negative_components_are_scaled_not_flipped() -> None:
    normalized = normalize([-3.0, 4.0])

    assert normalized[0] < 0
    assert math.isclose(l2_norm(normalized), 1.0)


def test_high_dimensional_vector_normalizes() -> None:
    normalized = normalize([1.0] * 768)

    assert math.isclose(l2_norm(normalized), 1.0)


def test_zero_vector_is_rejected() -> None:
    with pytest.raises(ZeroVectorError, match="zero-length"):
        normalize([0.0, 0.0, 0.0])


def test_vanishingly_small_vector_is_rejected() -> None:
    with pytest.raises(ZeroVectorError):
        normalize([1e-20, 1e-20])


def test_normalize_all_handles_a_batch() -> None:
    normalized = normalize_all([[3.0, 4.0], [1.0, 0.0]])

    assert all(is_normalized(vector) for vector in normalized)


def test_normalize_all_on_empty_batch() -> None:
    assert normalize_all([]) == []


def test_is_normalized_rejects_unscaled_vectors() -> None:
    assert is_normalized([3.0, 4.0]) is False


def test_is_normalized_tolerance_is_configurable() -> None:
    assert is_normalized([1.001, 0.0], tolerance=1e-2) is True
    assert is_normalized([1.001, 0.0], tolerance=1e-6) is False


def test_orthogonal_normalized_vectors_have_zero_similarity() -> None:
    similarity = cosine_similarity(normalize([1.0, 0.0]), normalize([0.0, 1.0]))

    assert similarity == pytest.approx(0.0)


def test_identical_normalized_vectors_have_similarity_one() -> None:
    vector = normalize([2.0, 3.0, 6.0])

    assert cosine_similarity(vector, vector) == pytest.approx(1.0)


def test_opposite_normalized_vectors_have_similarity_minus_one() -> None:
    similarity = cosine_similarity(normalize([1.0, 1.0]), normalize([-1.0, -1.0]))

    assert similarity == pytest.approx(-1.0)


def test_inner_product_equals_cosine_after_normalizing() -> None:
    left, right = [4.0, 0.0, 3.0], [1.0, 2.0, 2.0]
    expected = sum(a * b for a, b in zip(left, right, strict=True)) / (
        l2_norm(left) * l2_norm(right)
    )

    assert cosine_similarity(normalize(left), normalize(right)) == pytest.approx(expected)


def test_similarity_rejects_mismatched_dimensions() -> None:
    with pytest.raises(ValueError, match="dimension mismatch"):
        cosine_similarity([1.0, 0.0], [1.0, 0.0, 0.0])


def test_mean_vector_pools_a_segment_and_normalizes() -> None:
    pooled = mean_vector([[1.0, 0.0], [0.0, 1.0]])

    assert is_normalized(pooled) is True
    assert pooled == pytest.approx([0.7071067811865476, 0.7071067811865476])


def test_mean_of_identical_vectors_is_that_vector() -> None:
    vector = normalize([1.0, 2.0, 2.0])

    assert mean_vector([vector, vector, vector]) == pytest.approx(vector)


def test_pooled_segment_vector_is_close_to_its_frames() -> None:
    frames = [normalize([1.0, 0.1, 0.0]), normalize([1.0, 0.0, 0.1])]

    pooled = mean_vector(frames)

    assert all(cosine_similarity(pooled, frame) > 0.9 for frame in frames)


def test_mean_of_empty_set_is_rejected() -> None:
    with pytest.raises(ValueError, match="empty set"):
        mean_vector([])


def test_mean_rejects_ragged_dimensions() -> None:
    with pytest.raises(ValueError, match="same dimension"):
        mean_vector([[1.0, 0.0], [1.0, 0.0, 0.0]])


def test_mean_of_cancelling_vectors_is_rejected() -> None:
    with pytest.raises(ZeroVectorError):
        mean_vector([[1.0, 0.0], [-1.0, 0.0]])


def test_l2_norm_of_empty_vector_is_zero() -> None:
    assert l2_norm([]) == 0.0
