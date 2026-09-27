from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence
from enum import StrEnum

class DistanceMetric(StrEnum):
    L2 = "l2"
    COSINE = "cosine"
    INNER_PRODUCT = "ip"

@dataclass(frozen=True, slots=True)
class VectorSearchResult:
    id: str
    score: float


class VectorIndexPort(Protocol):

    def add_batch(
        self,
        ids: Sequence[str],
        vectors: Sequence[Sequence[float]],
    ) -> None:
        """批量添加向量。"""
        ...

    def delete_batch(
        self,
        ids: Sequence[str],
    ) -> None:
        """批量删除向量。"""
        ...

    def search(
        self,
        vector: Sequence[float],
        *,
        ids: Sequence[str] = None,
        limit: int = -1,
        score_threshold: float | None = None,
    ) -> Sequence[VectorSearchResult]:
        """相似度搜索。"""
        ...