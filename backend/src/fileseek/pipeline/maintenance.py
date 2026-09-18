"""Repairs the vector indexes after the library changes underneath them.

A consistency scan only marks files: it records what disappeared or was replaced
but leaves their vectors in place, because removing one entry from a flat index
rewrites the whole file. This module finishes that deferred work.

Three jobs:
- name the vectors search must ignore, so a file that is gone never surfaces
- drop those vectors for real, once it is worth one rewrite per index
- rebuild an index from the library when it is unreadable or was built by
  another model

The library is the only source of truth, so all three are recoverable operations:
every vector can be recomputed from the files themselves.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from fileseek.db.records import FileRecord, IndexState, MediaType
from fileseek.index.registry import INDEX_KINDS, IndexHealth, IndexKind
from fileseek.pipeline.context import IndexingContext, NullProgress, ProgressReporter
from fileseek.pipeline.documents import reindex_document
from fileseek.pipeline.images import reindex_image

# Both states leave vectors behind that no longer describe the file: 'missing' has
# no file at all, 'needs_reindex' has different bytes than what was encoded.
STALE_STATES: tuple[IndexState, ...] = ("missing", "needs_reindex")

# What a rebuild walks: everything that should end up searchable. 'missing' is
# excluded because there is nothing on disk left to encode.
REBUILDABLE_STATES: tuple[IndexState, ...] = ("indexed", "needs_reindex", "pending")

_MEDIA_FOR_KIND: dict[IndexKind, MediaType] = {
    "document": "document",
    "image": "image",
    "video_segment": "video",
}

# Re-encodes one library file back into its index. Video segments join this table
# when that pipeline lands; until then a rebuild of that kind is refused rather
# than silently emptying the index.
Reindexer = Callable[[FileRecord, IndexingContext, ProgressReporter], object]

_REINDEXERS: dict[IndexKind, Reindexer] = {
    "document": reindex_document,
    "image": reindex_image,
}


class RebuildNotSupportedError(NotImplementedError):
    """No pipeline can re-encode this kind yet, so its index must be left alone."""

    def __init__(self, kind: IndexKind) -> None:
        super().__init__(
            f"cannot rebuild the {kind} index: no reindexer is registered for it. "
            "Rebuilding without one would discard vectors that cannot be recomputed."
        )
        self.kind = kind


@dataclass(frozen=True)
class StaleVectors:
    """Vector ids that must be kept out of results, grouped by index."""

    by_kind: Mapping[IndexKind, frozenset[int]]

    def for_kind(self, kind: IndexKind) -> frozenset[int]:
        return self.by_kind.get(kind, frozenset())

    @property
    def total(self) -> int:
        return sum(len(ids) for ids in self.by_kind.values())

    @property
    def is_empty(self) -> bool:
        return self.total == 0


def stale_vector_ids(
    context: IndexingContext,
    states: Sequence[IndexState] = STALE_STATES,
) -> StaleVectors:
    """Collect the vectors whose files are no longer searchable.

    Pass the matching set to `IndexRegistry.search` as `excluded`: filtering at
    query time is what makes deferring the removal safe.
    """
    return StaleVectors(
        by_kind={
            "document": frozenset(context.chunks.vector_ids_by_state(states)),
            "image": frozenset(context.images.vector_ids_by_state(states)),
            "video_segment": frozenset(context.segments.vector_ids_by_state(states)),
        }
    )


@dataclass(frozen=True)
class PurgeResult:
    removed: Mapping[IndexKind, int]
    saved: tuple[Path, ...]

    @property
    def total_removed(self) -> int:
        return sum(self.removed.values())

    def describe(self) -> str:
        if not self.total_removed:
            return "no stale vectors to remove"
        parts = [f"{count} {kind}" for kind, count in self.removed.items() if count]
        return f"removed {', '.join(parts)} vectors"


def purge_stale_vectors(
    context: IndexingContext,
    states: Sequence[IndexState] = STALE_STATES,
) -> PurgeResult:
    """Drop the stale vectors from each index and persist the result.

    Only indexes that actually lost something are written, since saving rewrites
    the whole file. The metadata rows keep their vector_id: they record what was
    indexed, ids are never reused so nothing can alias them, and a later reindex
    overwrites them anyway.
    """
    stale = stale_vector_ids(context, states)
    removed: dict[IndexKind, int] = {}
    saved: list[Path] = []

    for kind in INDEX_KINDS:
        ids = sorted(stale.for_kind(kind))
        if not ids:
            continue
        count = context.registry.remove(kind, ids)
        removed[kind] = count
        if count:
            saved.append(context.registry.save(kind))

    return PurgeResult(removed=removed, saved=tuple(saved))


@dataclass(frozen=True)
class IndexStatus:
    """What the indexes look like at startup."""

    health: tuple[IndexHealth, ...]
    stale: StaleVectors

    @property
    def needs_rebuild(self) -> tuple[IndexKind, ...]:
        return tuple(entry.kind for entry in self.health if entry.needs_rebuild)

    @property
    def is_healthy(self) -> bool:
        return not self.needs_rebuild

    @property
    def total_vectors(self) -> int:
        return sum(entry.size for entry in self.health)

    def describe(self) -> str:
        if self.is_healthy:
            searchable = self.total_vectors - self.stale.total
            return f"{searchable} vectors searchable across {len(self.health)} indexes"
        return f"{', '.join(self.needs_rebuild)} need rebuilding"


def index_status(context: IndexingContext) -> IndexStatus:
    """Report index state without opening anything for writing.

    Safe to call on startup even when a tier switch or a corrupt file makes the
    indexes unusable: nothing here raises, so the UI can offer a rebuild instead
    of failing to start.
    """
    return IndexStatus(
        health=tuple(context.registry.health_report()),
        stale=stale_vector_ids(context),
    )


@dataclass(frozen=True)
class RebuildResult:
    kind: IndexKind
    reindexed: int
    # (file id, message) per file that could not be re-encoded.
    failures: tuple[tuple[str, str], ...]

    @property
    def attempted(self) -> int:
        return self.reindexed + len(self.failures)

    @property
    def is_complete(self) -> bool:
        return not self.failures

    def describe(self) -> str:
        if self.is_complete:
            return f"rebuilt the {self.kind} index from {self.reindexed} files"
        return (
            f"rebuilt the {self.kind} index from {self.reindexed} of "
            f"{self.attempted} files, {len(self.failures)} left pending"
        )


def rebuild_index(
    kind: IndexKind,
    context: IndexingContext,
    reindexers: Mapping[IndexKind, Reindexer] | None = None,
    progress: ProgressReporter | None = None,
    on_progress: Callable[[int, int], None] | None = None,
) -> RebuildResult:
    """Discard one index and re-encode every library file that belongs in it.

    This is the documented recovery from a corrupt index or a model change: the
    reset clears the recorded model, so writes are accepted again at the new
    tier's vector width.

    A file that cannot be re-encoded is left pending and reported rather than
    aborting the run, so one unreadable file does not strand the whole rebuild.
    """
    reindex = (reindexers if reindexers is not None else _REINDEXERS).get(kind)
    if reindex is None:
        raise RebuildNotSupportedError(kind)

    reporter = progress if progress is not None else NullProgress()
    records = context.files.list_by_media_type(
        _MEDIA_FOR_KIND[kind], limit=None, index_states=REBUILDABLE_STATES
    )

    # Reset before encoding: it drops the stale file and records the live model,
    # which is what lets the writes below through.
    context.registry.reset(kind)

    reindexed = 0
    failures: list[tuple[str, str]] = []
    for position, record in enumerate(records, start=1):
        try:
            reindex(record, context, reporter)
            reindexed += 1
        except (OSError, RuntimeError, ValueError) as error:
            context.files.set_index_state(record.id, "pending")
            failures.append((record.id, str(error)))
        if on_progress is not None:
            on_progress(position, len(records))

    # Save even when nothing was reindexed, so an empty rebuild leaves a readable
    # file behind rather than the absence the reset created.
    context.registry.save(kind)

    return RebuildResult(kind=kind, reindexed=reindexed, failures=tuple(failures))
