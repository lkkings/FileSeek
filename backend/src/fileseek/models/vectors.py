"""Vector normalisation.

Every vector is L2-normalised before it reaches an index, which makes the inner
product Faiss computes equal to cosine similarity (design decision 8).
"""

from __future__ import annotations

import math
from collections.abc import Sequence

# Below this a vector carries no direction, so normalising it would amplify noise.
MIN_NORM = 1e-12


class ZeroVectorError(ValueError):
    def __init__(self) -> None:
        super().__init__("cannot normalise a zero-length vector")


def l2_norm(vector: Sequence[float]) -> float:
    return math.sqrt(sum(component * component for component in vector))


def normalize(vector: Sequence[float]) -> list[float]:
    """Scale vector to unit length."""
    norm = l2_norm(vector)
    if norm < MIN_NORM:
        raise ZeroVectorError
    return [component / norm for component in vector]


def normalize_all(vectors: Sequence[Sequence[float]]) -> list[list[float]]:
    return [normalize(vector) for vector in vectors]


def is_normalized(vector: Sequence[float], tolerance: float = 1e-6) -> bool:
    return abs(l2_norm(vector) - 1.0) <= tolerance


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    """Inner product of two vectors, which equals cosine similarity once normalised."""
    if len(left) != len(right):
        raise ValueError(f"dimension mismatch: {len(left)} vs {len(right)}")
    return sum(a * b for a, b in zip(left, right, strict=True))


def mean_vector(vectors: Sequence[Sequence[float]]) -> list[float]:
    """Average several vectors and renormalise, used to pool a video segment."""
    if not vectors:
        raise ValueError("cannot average an empty set of vectors")
    width = len(vectors[0])
    if any(len(vector) != width for vector in vectors):
        raise ValueError("all vectors must have the same dimension")
    totals = [sum(vector[index] for vector in vectors) / len(vectors) for index in range(width)]
    return normalize(totals)
