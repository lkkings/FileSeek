"""A persisted vector index.

Wraps Faiss so entries are addressed by our own stable integer ids rather than
by insertion position: that is what makes removal and rebuild possible without
renumbering everything else. Vectors arrive already L2-normalised, so the inner
product Faiss computes is cosine similarity.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import faiss
import numpy as np

from fileseek.db.connection import require_local_path

# Faiss reports "no neighbour here" as this label.
_EMPTY_LABEL = -1


class IndexCorruptError(RuntimeError):
    """The index file on disk could not be read.

    Recoverable: every vector can be recomputed from the library files, so the
    caller is expected to offer a rebuild rather than treat this as data loss.
    """

    def __init__(self, path: Path, reason: str) -> None:
        super().__init__(
            f"vector index at {path} could not be read ({reason}). It can be rebuilt "
            "from the library."
        )
        self.path = path
        self.reason = reason


class DimensionMismatchError(ValueError):
    def __init__(self, expected: int, received: int) -> None:
        super().__init__(f"expected {expected}-dimensional vectors, received {received}")
        self.expected = expected
        self.received = received


@dataclass(frozen=True)
class SearchHit:
    vector_id: int
    score: float


def _as_matrix(vectors: Sequence[Sequence[float]], dimensions: int) -> np.ndarray[Any, Any]:
    if not vectors:
        return np.empty((0, dimensions), dtype=np.float32)
    width = len(vectors[0])
    if width != dimensions:
        raise DimensionMismatchError(dimensions, width)
    if any(len(vector) != dimensions for vector in vectors):
        raise DimensionMismatchError(dimensions, min(len(v) for v in vectors))
    return np.asarray(vectors, dtype=np.float32).reshape(len(vectors), dimensions)


class VectorIndex:
    """Exact inner-product search over unit vectors, addressed by stable ids.

    Exact rather than approximate on purpose: at the sizes this product targets
    a brute-force scan answers in milliseconds, with no training step and no
    recall loss (design decision 8).
    """

    def __init__(self, dimensions: int, index: faiss.Index | None = None) -> None:
        if dimensions < 1:
            raise ValueError(f"dimensions must be positive, got {dimensions}")
        self._dimensions = dimensions
        self._index = (
            index if index is not None else faiss.IndexIDMap2(faiss.IndexFlatIP(dimensions))
        )

    @property
    def dimensions(self) -> int:
        return self._dimensions

    @property
    def size(self) -> int:
        return int(self._index.ntotal)

    def add(self, vector_ids: Sequence[int], vectors: Sequence[Sequence[float]]) -> int:
        if len(vector_ids) != len(vectors):
            raise ValueError(
                f"got {len(vector_ids)} ids for {len(vectors)} vectors; they must match"
            )
        if not vectors:
            return 0
        matrix = _as_matrix(vectors, self._dimensions)
        self._index.add_with_ids(matrix, np.asarray(vector_ids, dtype=np.int64))
        return len(vectors)

    def search(self, query: Sequence[float], limit: int) -> list[SearchHit]:
        """The `limit` closest entries, best first."""
        if limit < 1:
            raise ValueError(f"limit must be positive, got {limit}")
        if self.size == 0:
            return []
        matrix = _as_matrix([query], self._dimensions)
        scores, labels = self._index.search(matrix, min(limit, self.size))
        return [
            SearchHit(vector_id=int(label), score=float(score))
            for label, score in zip(labels[0], scores[0], strict=True)
            if label != _EMPTY_LABEL
        ]

    def remove(self, vector_ids: Sequence[int]) -> int:
        if not vector_ids:
            return 0
        # `ids` must stay referenced: the selector holds a raw pointer into it.
        ids = np.asarray(vector_ids, dtype=np.int64)
        selector = faiss.IDSelectorBatch(len(ids), faiss.swig_ptr(ids))
        return int(self._index.remove_ids(selector))

    def reconstruct(self, vector_id: int) -> list[float] | None:
        """The stored vector, or None if that id is not present."""
        try:
            return [float(value) for value in self._index.reconstruct(int(vector_id))]
        except RuntimeError:
            return None

    def save(self, path: Path | str) -> Path:
        target = require_local_path(path, purpose="vector index")
        target.parent.mkdir(parents=True, exist_ok=True)
        # Write beside the target and rename, so a crash mid-write cannot leave a
        # half-written index where a readable one used to be.
        staging = target.with_name(target.name + ".writing")
        faiss.write_index(self._index, str(staging))
        staging.replace(target)
        return target

    @classmethod
    def load(cls, path: Path | str) -> VectorIndex:
        target = require_local_path(path, purpose="vector index")
        if not target.is_file():
            raise IndexCorruptError(target, "file does not exist")
        try:
            index = faiss.read_index(str(target))
        except RuntimeError as error:
            raise IndexCorruptError(target, str(error).split("\n", maxsplit=1)[0]) from error
        return cls(dimensions=int(index.d), index=index)

    @classmethod
    def load_or_create(cls, path: Path | str, dimensions: int) -> VectorIndex:
        """Load an existing index, or start an empty one when there is none yet."""
        target = Path(path)
        if not target.is_file():
            return cls(dimensions=dimensions)
        return cls.load(target)
