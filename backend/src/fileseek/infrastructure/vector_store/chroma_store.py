from __future__ import annotations

from pathlib import Path
from typing import Sequence

import chromadb
from chromadb.config import Settings as ChromaSettings

from fileseek.infrastructure.vector_store.base import (
    DistanceMetric,
    VectorIndexPort,
    VectorSearchResult,
)


class ChromaVectorStore(VectorIndexPort):
    """基于 ChromaDB 的向量索引实现。"""

    def __init__(
        self,
        persist_directory: Path,
        *,
        collection_name: str = "file",
        distance_metric: DistanceMetric = DistanceMetric.COSINE,
    ) -> None:
        persist_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._distance_metric = distance_metric

        self._client = chromadb.PersistentClient(
            path=str(persist_directory),
            settings=ChromaSettings(
                anonymized_telemetry=False,
            ),
        )

        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            configuration={
                "hnsw": {
                    "space": distance_metric.value,
                },
            },
        )

    # ============================================================
    # Write
    # ============================================================

    def add_batch(
        self,
        ids: Sequence[str],
        vectors: Sequence[Sequence[float]],
    ) -> None:
        """批量添加或更新向量。"""

        if len(ids) != len(vectors):
            raise ValueError(
                "ids and vectors must have the same length",
            )

        if not ids:
            return

        normalized_ids = list(ids)

        normalized_vectors = [
            list(vector)
            for vector in vectors
        ]

        for id_, vector in zip(
            normalized_ids,
            normalized_vectors,
            strict=True,
        ):
            if not vector:
                raise ValueError(
                    f"vector is empty: id={id_!r}",
                )

        self._collection.upsert(
            ids=normalized_ids,
            embeddings=normalized_vectors,
        )

    def delete_batch(
        self,
        ids: Sequence[str],
    ) -> None:
        """批量删除向量。"""

        if not ids:
            return

        self._collection.delete(
            ids=list(dict.fromkeys(ids)),
        )

    # ============================================================
    # Search
    # ============================================================

    def search(
        self,
        vector: Sequence[float],
        *,
        ids: Sequence[str] | None = None,
        limit: int = -1,
        score_threshold: float | None = None,
    ) -> Sequence[VectorSearchResult]:
        """执行向量相似度搜索。

        Args:
            vector:
                查询向量。

            ids:
                可选的候选 ID 集合。
                如果指定，只搜索这些 ID。

            limit:
                最大返回数量。
                -1 表示不限制。
                0 表示不返回结果。

            score_threshold:
                可选的最低分数。
                只返回 score >= score_threshold 的结果。

        Returns:
            按 score 从高到低排序的搜索结果。
        """

        if limit == 0:
            return []

        if limit < -1:
            raise ValueError(
                "limit must be -1 or greater than or equal to 0",
            )

        query_vector = list(vector)

        if not query_vector:
            raise ValueError(
                "vector must not be empty",
            )

        # --------------------------------------------------------
        # 全量 ANN 搜索
        # --------------------------------------------------------

        if ids is None:
            return self._search_all(
                vector=query_vector,
                limit=limit,
                score_threshold=score_threshold,
            )

        # --------------------------------------------------------
        # 指定 ID 搜索
        # --------------------------------------------------------

        candidate_ids = list(
            dict.fromkeys(ids),
        )

        if not candidate_ids:
            return []

        return self._search_ids(
            vector=query_vector,
            ids=candidate_ids,
            limit=limit,
            score_threshold=score_threshold,
        )

    # ============================================================
    # Internal search
    # ============================================================

    def _search_all(
        self,
        *,
        vector: list[float],
        limit: int,
        score_threshold: float | None,
    ) -> list[VectorSearchResult]:
        """在整个 collection 中执行 ANN 搜索。"""

        count = self._collection.count()

        if count == 0:
            return []

        n_results = (
            count
            if limit == -1
            else min(limit, count)
        )

        result = self._collection.query(
            query_embeddings=[vector],
            n_results=n_results,
            include=["distances"],
        )

        result_ids = result["ids"][0]
        distances = result["distances"][0]

        results: list[VectorSearchResult] = []

        for id_, distance in zip(
            result_ids,
            distances,
            strict=True,
        ):
            score = self._distance_to_score(distance)

            if (
                score_threshold is not None
                and score < score_threshold
            ):
                continue

            results.append(
                VectorSearchResult(
                    id=id_,
                    score=score,
                )
            )

        # score 越高越相似。
        results.sort(
            key=lambda item: item.score,
            reverse=True,
        )

        return results

    def _search_ids(
        self,
        *,
        vector: list[float],
        ids: list[str],
        limit: int,
        score_threshold: float | None,
    ) -> list[VectorSearchResult]:
        """只在指定 ID 集合中执行搜索。

        Chroma 的 query() 不支持直接把 IDs 作为候选集合。
        因此先通过 get() 获取指定向量，再在本地计算距离。
        """

        data = self._collection.get(
            ids=ids,
            include=["embeddings"],
        )

        result_ids = data["ids"]
        embeddings = data["embeddings"]

        if not result_ids:
            return []

        results: list[VectorSearchResult] = []

        for id_, embedding in zip(
            result_ids,
            embeddings,
            strict=True,
        ):
            if embedding is None:
                continue

            distance = self._calculate_distance(
                vector,
                embedding,
            )

            score = self._distance_to_score(distance)

            if (
                score_threshold is not None
                and score < score_threshold
            ):
                continue

            results.append(
                VectorSearchResult(
                    id=id_,
                    score=score,
                )
            )

        # score 越高越相似。
        results.sort(
            key=lambda item: item.score,
            reverse=True,
        )

        if limit == -1:
            return results

        return results[:limit]

    # ============================================================
    # Distance / Score
    # ============================================================

    def _distance_to_score(
        self,
        distance: float,
    ) -> float:
        """将 Chroma distance 转换成统一的 similarity score。

        对外约定：
            score 越高，表示越相似。
        """

        if self._distance_metric == DistanceMetric.COSINE:
            # distance = 1 - cosine_similarity
            return 1.0 - distance

        if self._distance_metric == DistanceMetric.IP:
            # distance = 1 - inner_product
            return 1.0 - distance

        if self._distance_metric == DistanceMetric.L2:
            # L2 distance 越小越相似。
            # 使用负距离统一成 score 越高越相似。
            return -distance

        raise ValueError(
            f"unsupported distance metric: "
            f"{self._distance_metric!r}",
        )

    def _calculate_distance(
        self,
        a: Sequence[float],
        b: Sequence[float],
    ) -> float:
        """计算两个向量之间的 Chroma distance。"""

        if len(a) != len(b):
            raise ValueError(
                "vector dimensions do not match: "
                f"{len(a)} != {len(b)}",
            )

        if self._distance_metric == DistanceMetric.COSINE:
            return self._cosine_distance(
                a,
                b,
            )

        if self._distance_metric == DistanceMetric.L2:
            return self._l2_distance(
                a,
                b,
            )

        if self._distance_metric == DistanceMetric.IP:
            return self._inner_product_distance(
                a,
                b,
            )

        raise ValueError(
            f"unsupported distance metric: "
            f"{self._distance_metric!r}",
        )

    @staticmethod
    def _cosine_distance(
        a: Sequence[float],
        b: Sequence[float],
    ) -> float:
        """Cosine distance = 1 - cosine similarity."""

        dot = 0.0
        norm_a = 0.0
        norm_b = 0.0

        for x, y in zip(
            a,
            b,
            strict=True,
        ):
            dot += x * y
            norm_a += x * x
            norm_b += y * y

        if norm_a == 0.0 or norm_b == 0.0:
            raise ValueError(
                "cosine distance is undefined for zero vector",
            )

        similarity = (
            dot
            / (norm_a ** 0.5)
            / (norm_b ** 0.5)
        )

        return 1.0 - similarity

    @staticmethod
    def _l2_distance(
        a: Sequence[float],
        b: Sequence[float],
    ) -> float:
        """Squared L2 distance。

        Chroma 的 L2 space 使用平方欧氏距离，
        因此这里不执行 sqrt。
        """

        return sum(
            (x - y) ** 2
            for x, y in zip(
                a,
                b,
                strict=True,
            )
        )

    @staticmethod
    def _inner_product_distance(
        a: Sequence[float],
        b: Sequence[float],
    ) -> float:
        """Inner product distance。

        Chroma 使用：
            distance = 1 - inner_product
        """

        return 1.0 - sum(
            x * y
            for x, y in zip(
                a,
                b,
                strict=True,
            )
        )