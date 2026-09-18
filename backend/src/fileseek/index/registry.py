"""Owns the three vector indexes and the metadata that keeps them coherent.

Documents, images and video segments are indexed separately: their vectors come
from different models and different semantic spaces, and keeping them apart turns
"search only videos" into picking an index rather than filtering results.

Each index records which model produced it. Mixing vectors from two models into
one index would silently wreck similarity, so a tier change is detected on load
and blocks writes until the index is rebuilt.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from fileseek.index.store import IndexCorruptError, SearchHit, VectorIndex
from fileseek.models.tiers import ModelBundle

IndexKind = Literal["document", "image", "video_segment"]

INDEX_KINDS: tuple[IndexKind, ...] = ("document", "image", "video_segment")

_FILENAMES: dict[IndexKind, str] = {
    "document": "documents.faiss",
    "image": "images.faiss",
    "video_segment": "video_segments.faiss",
}

_MODEL_KEY = "index_model"
_DIMS_KEY = "index_dims"
_SEQ_KEY = "vector_id_seq"


class ModelMismatchError(RuntimeError):
    """The index was built by a different model than the one now loaded."""

    def __init__(self, kind: IndexKind, recorded: str, current: str) -> None:
        super().__init__(
            f"the {kind} index was built with {recorded}, but {current} is now active. "
            "Rebuild the index before adding more vectors."
        )
        self.kind = kind
        self.recorded = recorded
        self.current = current


@dataclass(frozen=True)
class IndexHealth:
    kind: IndexKind
    size: int
    is_readable: bool
    is_compatible: bool
    recorded_model: str | None = None
    current_model: str | None = None
    problem: str | None = None

    @property
    def needs_rebuild(self) -> bool:
        return not (self.is_readable and self.is_compatible)

    def describe(self) -> str:
        if self.is_compatible and self.is_readable:
            return f"{self.kind} index holds {self.size} vectors"
        return f"{self.kind} index needs rebuilding: {self.problem}"


def _model_for(kind: IndexKind, bundle: ModelBundle) -> tuple[str, int]:
    """Which model feeds this index, and how wide its vectors are."""
    if kind == "document":
        return bundle.text.repo_id, bundle.text_dimensions
    return bundle.image.repo_id, bundle.image_dimensions


class IndexRegistry:
    """Opens, records and rebuilds the three indexes as one unit."""

    def __init__(
        self,
        index_dir: Path,
        connection: sqlite3.Connection,
        bundle: ModelBundle,
    ) -> None:
        self._dir = index_dir
        self._connection = connection
        self._bundle = bundle
        self._open: dict[IndexKind, VectorIndex] = {}

    @property
    def bundle(self) -> ModelBundle:
        return self._bundle

    def path_for(self, kind: IndexKind) -> Path:
        return self._dir / _FILENAMES[kind]

    def _meta(self, key: str, kind: IndexKind) -> str | None:
        row = self._connection.execute(
            "SELECT value FROM schema_meta WHERE key = ?", (f"{key}:{kind}",)
        ).fetchone()
        return None if row is None else str(row["value"])

    def _set_meta(self, key: str, kind: IndexKind, value: str) -> None:
        self._connection.execute(
            "INSERT INTO schema_meta (key, value) VALUES (?, ?) "
            "ON CONFLICT (key) DO UPDATE SET value = excluded.value",
            (f"{key}:{kind}", value),
        )

    def recorded_model(self, kind: IndexKind) -> str | None:
        return self._meta(_MODEL_KEY, kind)

    def recorded_dimensions(self, kind: IndexKind) -> int | None:
        raw = self._meta(_DIMS_KEY, kind)
        return None if raw is None else int(raw)

    def record_model(self, kind: IndexKind) -> None:
        repo_id, dimensions = _model_for(kind, self._bundle)
        self._set_meta(_MODEL_KEY, kind, repo_id)
        self._set_meta(_DIMS_KEY, kind, str(dimensions))

    def is_compatible(self, kind: IndexKind) -> bool:
        """True when nothing is recorded yet, or the record matches the live model."""
        recorded = self.recorded_model(kind)
        if recorded is None:
            return True
        current, _ = _model_for(kind, self._bundle)
        return recorded == current

    def ensure_compatible(self, kind: IndexKind) -> None:
        if not self.is_compatible(kind):
            recorded = self.recorded_model(kind)
            current, _ = _model_for(kind, self._bundle)
            raise ModelMismatchError(kind, recorded or "unknown", current)

    def allocate_ids(self, kind: IndexKind, count: int) -> list[int]:
        """Hand out ids that are never reused.

        Reuse would let a removed entry's id alias a new one, so the sequence only
        ever moves forward.
        """
        if count < 0:
            raise ValueError(f"count must not be negative, got {count}")
        if count == 0:
            return []
        raw = self._meta(_SEQ_KEY, kind)
        start = 1 if raw is None else int(raw) + 1
        self._set_meta(_SEQ_KEY, kind, str(start + count - 1))
        return list(range(start, start + count))

    def open(self, kind: IndexKind) -> VectorIndex:
        """Open an index for reading and writing, refusing a model mismatch."""
        self.ensure_compatible(kind)
        if kind not in self._open:
            _, dimensions = _model_for(kind, self._bundle)
            self._open[kind] = VectorIndex.load_or_create(self.path_for(kind), dimensions)
            self.record_model(kind)
        return self._open[kind]

    def add(
        self,
        kind: IndexKind,
        vector_ids: Sequence[int],
        vectors: Sequence[Sequence[float]],
    ) -> int:
        return self.open(kind).add(vector_ids, vectors)

    def search(
        self,
        kind: IndexKind,
        query: Sequence[float],
        limit: int,
        excluded: frozenset[int] = frozenset(),
    ) -> list[SearchHit]:
        """Search one index, dropping hits whose files are gone.

        Removal from a flat index rewrites it, so entries for missing files stay in
        place and are filtered here instead (design decision: mark, then batch).
        Over-fetching keeps the result count honest once exclusions are dropped.
        """
        index = self.open(kind)
        if not excluded:
            return index.search(query, limit)
        hits = index.search(query, limit + len(excluded))
        kept = [hit for hit in hits if hit.vector_id not in excluded]
        return kept[:limit]

    def remove(self, kind: IndexKind, vector_ids: Sequence[int]) -> int:
        return self.open(kind).remove(vector_ids)

    def save(self, kind: IndexKind) -> Path:
        return self.open(kind).save(self.path_for(kind))

    def save_all(self) -> list[Path]:
        return [index.save(self.path_for(kind)) for kind, index in self._open.items()]

    def health(self, kind: IndexKind) -> IndexHealth:
        """Report whether this index is usable, without raising."""
        current, _ = _model_for(kind, self._bundle)
        recorded = self.recorded_model(kind)

        if recorded is not None and recorded != current:
            return IndexHealth(
                kind=kind,
                size=0,
                is_readable=True,
                is_compatible=False,
                recorded_model=recorded,
                current_model=current,
                problem=f"built with {recorded}, now running {current}",
            )

        path = self.path_for(kind)
        if not path.is_file():
            return IndexHealth(
                kind=kind,
                size=0,
                is_readable=True,
                is_compatible=True,
                recorded_model=recorded,
                current_model=current,
            )

        try:
            index = VectorIndex.load(path)
        except IndexCorruptError as error:
            return IndexHealth(
                kind=kind,
                size=0,
                is_readable=False,
                is_compatible=True,
                recorded_model=recorded,
                current_model=current,
                problem=error.reason,
            )

        return IndexHealth(
            kind=kind,
            size=index.size,
            is_readable=True,
            is_compatible=True,
            recorded_model=recorded,
            current_model=current,
        )

    def health_report(self) -> list[IndexHealth]:
        return [self.health(kind) for kind in INDEX_KINDS]

    def reset(self, kind: IndexKind) -> VectorIndex:
        """Discard an index so it can be rebuilt from the library files."""
        self.path_for(kind).unlink(missing_ok=True)
        self._open.pop(kind, None)
        _, dimensions = _model_for(kind, self._bundle)
        fresh = VectorIndex(dimensions=dimensions)
        self._open[kind] = fresh
        self.record_model(kind)
        return fresh

    def close(self) -> None:
        self._open.clear()
