import sqlite3
from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest
from PIL import Image

from fileseek.db import (
    ChunkRepository,
    DocumentRepository,
    FileRepository,
    ImageRepository,
    SegmentRepository,
    VideoRepository,
    connect,
    migrate,
)
from fileseek.db.records import (
    ChunkRecord,
    DocumentRecord,
    FileRecord,
    IndexState,
    SegmentRecord,
    VideoRecord,
)
from fileseek.index.registry import IndexRegistry
from fileseek.library.layout import LibraryLayout
from fileseek.models.tiers import CPU_BUNDLE, GPU_BUNDLE, ModelBundle
from fileseek.models.vectors import normalize
from fileseek.pipeline.context import IndexingContext
from fileseek.pipeline.documents import index_document
from fileseek.pipeline.images import index_image
from fileseek.pipeline.maintenance import (
    REBUILDABLE_STATES,
    STALE_STATES,
    RebuildNotSupportedError,
    index_status,
    purge_stale_vectors,
    rebuild_index,
    stale_vector_ids,
)

IMAGE_WIDTH = CPU_BUNDLE.image_dimensions
TEXT_WIDTH = CPU_BUNDLE.text_dimensions


class DimensionedEncoder:
    """Deterministic vectors of the real width, so they fit the actual index.

    The width follows the bundle, because a rebuild after a tier switch feeds a
    wider index and a fixed width would fail for the wrong reason.
    """

    def __init__(self, bundle: ModelBundle = CPU_BUNDLE) -> None:
        self.bundle = bundle
        self.image_batches: list[int] = []

    def _seeded(self, seed: int, width: int) -> list[float]:
        raw = [1.0 if index == seed % width else 0.25 for index in range(width)]
        return normalize(raw)

    def encode_images(self, images: Sequence[bytes]) -> list[list[float]]:
        self.image_batches.append(len(images))
        return [self._seeded(len(payload), self.bundle.image_dimensions) for payload in images]

    def encode_texts(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._seeded(len(text), self.bundle.text_dimensions) for text in texts]

    def recognize_text(self, image: bytes) -> str:  # noqa: ARG002 - not under test here
        return ""


class BrokenEncoder(DimensionedEncoder):
    """Fails on every image, standing in for an unreadable file mid-rebuild."""

    def encode_images(self, images: Sequence[bytes]) -> list[list[float]]:
        raise RuntimeError("could not decode image")


def unit(dimensions: int, axis: int) -> list[float]:
    return normalize([float(n == axis) for n in range(dimensions)])


@pytest.fixture
def db() -> Iterator[sqlite3.Connection]:
    connection = connect(":memory:")
    migrate(connection)
    yield connection
    connection.close()


@pytest.fixture
def encoder() -> DimensionedEncoder:
    return DimensionedEncoder()


def make_context(
    tmp_path: Path,
    db: sqlite3.Connection,
    encoder: DimensionedEncoder,
    bundle: ModelBundle = CPU_BUNDLE,
) -> IndexingContext:
    layout = LibraryLayout(root=tmp_path / "library").initialize()
    return IndexingContext(
        layout=layout,
        files=FileRepository(db),
        images=ImageRepository(db),
        documents=DocumentRepository(db),
        videos=VideoRepository(db),
        segments=SegmentRepository(db),
        chunks=ChunkRepository(db),
        registry=IndexRegistry(tmp_path / "index", db, bundle),
        encoder=encoder,
    )


@pytest.fixture
def context(tmp_path: Path, db: sqlite3.Connection, encoder: DimensionedEncoder) -> IndexingContext:
    return make_context(tmp_path, db, encoder)


@pytest.fixture
def incoming(tmp_path: Path) -> Path:
    directory = tmp_path / "downloads"
    directory.mkdir()
    return directory


def write_image(
    directory: Path,
    name: str = "cat.jpg",
    size: tuple[int, int] = (320, 240),
    colour: tuple[int, int, int] = (220, 30, 30),
) -> Path:
    path = directory / name
    Image.new("RGB", size, colour).save(path)
    return path


def add_document(
    context: IndexingContext, file_id: str, vector_id: int, state: IndexState = "indexed"
) -> None:
    """A document with one chunk, which is the smallest searchable unit."""
    context.files.add(
        FileRecord(
            id=file_id,
            path=f"/library/documents/{file_id}.pdf",
            filename=f"{file_id}.pdf",
            media_type="document",
            size=1024,
            content_hash=f"hash-{file_id}",
            added_at=1,
            index_state=state,
        )
    )
    context.documents.upsert(DocumentRecord(file_id=file_id, text_content="body", chunk_count=1))
    context.chunks.add_many(
        [
            ChunkRecord(
                id=f"{file_id}-chunk",
                file_id=file_id,
                chunk_index=0,
                char_start=0,
                char_end=4,
                vector_id=vector_id,
            )
        ]
    )
    context.registry.add("document", [vector_id], [unit(TEXT_WIDTH, vector_id % TEXT_WIDTH)])


def add_video(
    context: IndexingContext, file_id: str, vector_id: int, state: IndexState = "indexed"
) -> None:
    context.files.add(
        FileRecord(
            id=file_id,
            path=f"/library/videos/{file_id}.mp4",
            filename=f"{file_id}.mp4",
            media_type="video",
            size=4096,
            content_hash=f"hash-{file_id}",
            added_at=1,
            index_state=state,
        )
    )
    context.videos.upsert(VideoRecord(file_id=file_id, duration=10.0, width=640, height=480))
    context.segments.add_many(
        [
            SegmentRecord(
                id=f"{file_id}-segment",
                video_id=file_id,
                start_time=0.0,
                end_time=5.0,
                vector_id=vector_id,
            )
        ]
    )
    context.registry.add("video_segment", [vector_id], [unit(IMAGE_WIDTH, vector_id % IMAGE_WIDTH)])


# --- stale vector collection -------------------------------------------------


def test_a_healthy_library_has_no_stale_vectors(context: IndexingContext, incoming: Path) -> None:
    index_image(write_image(incoming), context)

    assert stale_vector_ids(context).is_empty


def test_a_missing_file_makes_its_vector_stale(context: IndexingContext, incoming: Path) -> None:
    result = index_image(write_image(incoming), context)
    context.files.set_index_state(result.record.id, "missing")

    stale = stale_vector_ids(context)

    assert stale.for_kind("image") == frozenset({result.vector_id})


def test_a_replaced_file_makes_its_vector_stale(context: IndexingContext, incoming: Path) -> None:
    """needs_reindex means the bytes changed, so the old vector describes nothing."""
    result = index_image(write_image(incoming), context)
    context.files.set_index_state(result.record.id, "needs_reindex")

    assert stale_vector_ids(context).for_kind("image") == frozenset({result.vector_id})


def test_stale_vectors_are_grouped_by_index(context: IndexingContext, incoming: Path) -> None:
    image = index_image(write_image(incoming), context)
    add_document(context, "doc-1", vector_id=1, state="missing")
    add_video(context, "vid-1", vector_id=1, state="missing")
    context.files.set_index_state(image.record.id, "missing")

    stale = stale_vector_ids(context)

    assert stale.for_kind("document") == frozenset({1})
    assert stale.for_kind("video_segment") == frozenset({1})
    assert stale.for_kind("image") == frozenset({image.vector_id})
    assert stale.total == 3


def test_healthy_files_are_left_out_of_the_stale_set(
    context: IndexingContext, incoming: Path
) -> None:
    kept = index_image(write_image(incoming, name="kept.jpg"), context)
    gone = index_image(write_image(incoming, name="gone.jpg", colour=(10, 200, 40)), context)
    context.files.set_index_state(gone.record.id, "missing")

    stale = stale_vector_ids(context).for_kind("image")

    assert kept.vector_id not in stale
    assert gone.vector_id in stale


def test_a_kind_with_no_stale_vectors_reports_an_empty_set(context: IndexingContext) -> None:
    assert stale_vector_ids(context).for_kind("document") == frozenset()


def test_the_states_treated_as_stale_are_the_two_broken_ones() -> None:
    assert set(STALE_STATES) == {"missing", "needs_reindex"}


# --- search filtering, which is what makes deferral safe ---------------------


def test_search_excluding_stale_ids_hides_a_missing_file(
    context: IndexingContext, incoming: Path
) -> None:
    gone = index_image(write_image(incoming, name="gone.jpg"), context)
    context.files.set_index_state(gone.record.id, "missing")
    stale = stale_vector_ids(context)

    assert gone.vector_id is not None
    vector = context.registry.open("image").reconstruct(gone.vector_id)
    assert vector is not None
    hits = context.registry.search("image", vector, limit=5, excluded=stale.for_kind("image"))

    assert gone.vector_id not in {hit.vector_id for hit in hits}


def test_the_vector_is_still_in_the_index_until_purged(
    context: IndexingContext, incoming: Path
) -> None:
    """Filtering is a query-time concern; the file itself is untouched."""
    gone = index_image(write_image(incoming), context)
    context.files.set_index_state(gone.record.id, "missing")

    stale_vector_ids(context)

    assert context.registry.open("image").size == 1


# --- purging -----------------------------------------------------------------


def test_purging_removes_the_stale_vector(context: IndexingContext, incoming: Path) -> None:
    gone = index_image(write_image(incoming), context)
    context.files.set_index_state(gone.record.id, "missing")

    result = purge_stale_vectors(context)

    assert result.total_removed == 1
    assert context.registry.open("image").size == 0


def test_purging_keeps_the_healthy_vectors(context: IndexingContext, incoming: Path) -> None:
    kept = index_image(write_image(incoming, name="kept.jpg"), context)
    gone = index_image(write_image(incoming, name="gone.jpg", colour=(10, 200, 40)), context)
    context.files.set_index_state(gone.record.id, "missing")

    purge_stale_vectors(context)

    assert kept.vector_id is not None
    assert context.registry.open("image").reconstruct(kept.vector_id) is not None


def test_purging_a_clean_library_removes_nothing(context: IndexingContext, incoming: Path) -> None:
    index_image(write_image(incoming), context)

    result = purge_stale_vectors(context)

    assert result.total_removed == 0
    assert result.describe() == "no stale vectors to remove"


def test_purging_writes_only_the_indexes_that_changed(
    context: IndexingContext, incoming: Path
) -> None:
    """Saving rewrites a whole index file, so untouched kinds are left alone."""
    gone = index_image(write_image(incoming), context)
    add_document(context, "doc-1", vector_id=1)
    context.files.set_index_state(gone.record.id, "missing")

    result = purge_stale_vectors(context)

    assert result.saved == (context.registry.path_for("image"),)


def test_purged_vectors_stay_gone_after_a_reopen(
    tmp_path: Path, db: sqlite3.Connection, encoder: DimensionedEncoder, incoming: Path
) -> None:
    context = make_context(tmp_path, db, encoder)
    gone = index_image(write_image(incoming), context)
    context.files.set_index_state(gone.record.id, "missing")
    purge_stale_vectors(context)

    reopened = IndexRegistry(tmp_path / "index", db, CPU_BUNDLE)

    assert reopened.open("image").size == 0


def test_purging_spans_every_index(context: IndexingContext, incoming: Path) -> None:
    image = index_image(write_image(incoming), context)
    add_document(context, "doc-1", vector_id=1, state="missing")
    add_video(context, "vid-1", vector_id=1, state="missing")
    context.files.set_index_state(image.record.id, "missing")

    result = purge_stale_vectors(context)

    assert result.total_removed == 3
    assert set(result.removed) == {"document", "image", "video_segment"}


def test_purge_description_names_what_went(context: IndexingContext, incoming: Path) -> None:
    gone = index_image(write_image(incoming), context)
    context.files.set_index_state(gone.record.id, "missing")

    assert "1 image" in purge_stale_vectors(context).describe()


def test_purging_leaves_the_metadata_row_in_place(context: IndexingContext, incoming: Path) -> None:
    """The row records what was indexed; ids are never reused, so it cannot alias."""
    gone = index_image(write_image(incoming), context)
    context.files.set_index_state(gone.record.id, "missing")

    purge_stale_vectors(context)

    stored = context.images.get(gone.record.id)
    assert stored is not None
    assert stored.vector_id == gone.vector_id


def test_purging_can_be_limited_to_one_state(context: IndexingContext, incoming: Path) -> None:
    replaced = index_image(write_image(incoming, name="replaced.jpg"), context)
    context.files.set_index_state(replaced.record.id, "needs_reindex")

    result = purge_stale_vectors(context, states=("missing",))

    assert result.total_removed == 0


# --- startup status ----------------------------------------------------------


def test_status_reports_a_fresh_install_as_healthy(context: IndexingContext) -> None:
    status = index_status(context)

    assert status.is_healthy
    assert status.needs_rebuild == ()
    assert status.total_vectors == 0


def test_status_counts_indexed_vectors(context: IndexingContext, incoming: Path) -> None:
    index_image(write_image(incoming), context)
    context.registry.save("image")

    assert index_status(context).total_vectors == 1


def test_status_subtracts_stale_vectors_from_what_is_searchable(
    context: IndexingContext, incoming: Path
) -> None:
    kept = index_image(write_image(incoming, name="kept.jpg"), context)
    gone = index_image(write_image(incoming, name="gone.jpg", colour=(10, 200, 40)), context)
    context.files.set_index_state(gone.record.id, "missing")
    context.registry.save("image")

    status = index_status(context)

    assert status.total_vectors == 2
    assert "1 vectors searchable" in status.describe()
    assert kept.vector_id is not None


def test_status_flags_a_corrupt_index(
    tmp_path: Path, db: sqlite3.Connection, encoder: DimensionedEncoder
) -> None:
    context = make_context(tmp_path, db, encoder)
    target = context.registry.path_for("image")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"not an index")

    status = index_status(context)

    assert status.needs_rebuild == ("image",)
    assert not status.is_healthy


def test_status_flags_a_tier_switch(
    tmp_path: Path, db: sqlite3.Connection, encoder: DimensionedEncoder, incoming: Path
) -> None:
    before = make_context(tmp_path, db, encoder)
    index_image(write_image(incoming), before)

    after = make_context(tmp_path, db, encoder, bundle=GPU_BUNDLE)
    status = index_status(after)

    assert "image" in status.needs_rebuild
    assert "need rebuilding" in status.describe()


def test_status_does_not_raise_on_an_unusable_index(
    tmp_path: Path, db: sqlite3.Connection, encoder: DimensionedEncoder, incoming: Path
) -> None:
    """Startup must be able to report the problem instead of failing to boot."""
    before = make_context(tmp_path, db, encoder)
    index_image(write_image(incoming), before)

    after = make_context(tmp_path, db, encoder, bundle=GPU_BUNDLE)

    assert after.registry.health("image").needs_rebuild is True
    assert index_status(after).needs_rebuild == ("image",)


def test_status_covers_every_index(context: IndexingContext) -> None:
    assert len(index_status(context).health) == 3


# --- rebuilding --------------------------------------------------------------


def test_rebuild_reencodes_the_library(context: IndexingContext, incoming: Path) -> None:
    index_image(write_image(incoming, name="one.jpg"), context)
    index_image(write_image(incoming, name="two.jpg", colour=(10, 200, 40)), context)

    result = rebuild_index("image", context)

    assert result.reindexed == 2
    assert context.registry.open("image").size == 2


def test_rebuild_restores_search_after_the_file_is_deleted(
    context: IndexingContext, incoming: Path
) -> None:
    indexed = index_image(write_image(incoming), context)
    context.registry.save("image")
    context.registry.path_for("image").unlink()
    context.registry.close()

    rebuild_index("image", context)

    stored = context.images.get(indexed.record.id)
    assert stored is not None
    assert stored.vector_id is not None
    vector = context.registry.open("image").reconstruct(stored.vector_id)
    assert vector is not None
    hits = context.registry.search("image", vector, limit=1)
    assert [hit.vector_id for hit in hits] == [stored.vector_id]


def test_rebuild_issues_fresh_vector_ids(context: IndexingContext, incoming: Path) -> None:
    """Ids are never reused, so a rebuilt entry gets a new one."""
    first = index_image(write_image(incoming), context)

    rebuild_index("image", context)

    stored = context.images.get(first.record.id)
    assert stored is not None
    assert stored.vector_id != first.vector_id


def test_rebuild_drops_the_old_index_file(context: IndexingContext, incoming: Path) -> None:
    index_image(write_image(incoming), context)
    context.registry.save("image")

    rebuild_index("image", context)

    assert context.registry.open("image").size == 1


def test_rebuild_after_a_tier_switch_is_accepted(
    tmp_path: Path, db: sqlite3.Connection, encoder: DimensionedEncoder, incoming: Path
) -> None:
    """A model change blocks writes; the rebuild is the documented way through."""
    before = make_context(tmp_path, db, encoder)
    index_image(write_image(incoming), before)
    before.registry.save("image")

    after = make_context(tmp_path, db, DimensionedEncoder(GPU_BUNDLE), bundle=GPU_BUNDLE)
    result = rebuild_index("image", after)

    assert result.is_complete
    assert after.registry.is_compatible("image") is True
    assert after.registry.recorded_model("image") == GPU_BUNDLE.image.repo_id


def test_rebuild_ignores_files_that_are_gone(context: IndexingContext, incoming: Path) -> None:
    """A missing file has nothing on disk to encode, so it is skipped, not failed."""
    gone = index_image(write_image(incoming, name="gone.jpg"), context)
    index_image(write_image(incoming, name="here.jpg", colour=(10, 200, 40)), context)
    context.files.set_index_state(gone.record.id, "missing")

    result = rebuild_index("image", context)

    assert result.attempted == 1
    assert result.reindexed == 1


def test_rebuild_includes_files_awaiting_indexing(context: IndexingContext, incoming: Path) -> None:
    indexed = index_image(write_image(incoming), context)
    context.files.set_index_state(indexed.record.id, "pending")

    assert rebuild_index("image", context).reindexed == 1


def test_rebuild_includes_replaced_files(context: IndexingContext, incoming: Path) -> None:
    indexed = index_image(write_image(incoming), context)
    context.files.set_index_state(indexed.record.id, "needs_reindex")

    result = rebuild_index("image", context)

    assert result.reindexed == 1
    record = context.files.get(indexed.record.id)
    assert record is not None
    assert record.index_state == "indexed"


def test_rebuild_of_an_empty_library_leaves_a_readable_index(context: IndexingContext) -> None:
    result = rebuild_index("image", context)

    assert result.reindexed == 0
    assert result.is_complete
    assert context.registry.path_for("image").is_file()


def test_one_unreadable_file_does_not_strand_the_rebuild(
    tmp_path: Path, db: sqlite3.Connection, incoming: Path
) -> None:
    good = make_context(tmp_path, db, DimensionedEncoder())
    index_image(write_image(incoming), good)

    broken = make_context(tmp_path, db, BrokenEncoder())
    result = rebuild_index("image", broken)

    assert result.reindexed == 0
    assert len(result.failures) == 1
    assert not result.is_complete


def test_a_file_that_fails_to_reencode_is_left_pending(
    tmp_path: Path, db: sqlite3.Connection, incoming: Path
) -> None:
    good = make_context(tmp_path, db, DimensionedEncoder())
    indexed = index_image(write_image(incoming), good)

    broken = make_context(tmp_path, db, BrokenEncoder())
    rebuild_index("image", broken)

    record = broken.files.get(indexed.record.id)
    assert record is not None
    assert record.index_state == "pending"


def test_a_failure_names_the_file_and_the_reason(
    tmp_path: Path, db: sqlite3.Connection, incoming: Path
) -> None:
    good = make_context(tmp_path, db, DimensionedEncoder())
    indexed = index_image(write_image(incoming), good)

    broken = make_context(tmp_path, db, BrokenEncoder())
    result = rebuild_index("image", broken)

    file_id, message = result.failures[0]
    assert file_id == indexed.record.id
    assert "could not decode image" in message


def test_rebuild_reports_progress_per_file(context: IndexingContext, incoming: Path) -> None:
    index_image(write_image(incoming, name="one.jpg"), context)
    index_image(write_image(incoming, name="two.jpg", colour=(10, 200, 40)), context)
    seen: list[tuple[int, int]] = []

    rebuild_index("image", context, on_progress=lambda done, total: seen.append((done, total)))

    assert seen == [(1, 2), (2, 2)]


def test_rebuild_description_reports_a_clean_run(context: IndexingContext, incoming: Path) -> None:
    index_image(write_image(incoming), context)

    assert "from 1 files" in rebuild_index("image", context).describe()


def test_rebuild_description_reports_what_was_left_behind(
    tmp_path: Path, db: sqlite3.Connection, incoming: Path
) -> None:
    good = make_context(tmp_path, db, DimensionedEncoder())
    index_image(write_image(incoming), good)

    broken = make_context(tmp_path, db, BrokenEncoder())

    assert "1 left pending" in rebuild_index("image", broken).describe()


def test_rebuilding_a_kind_with_no_pipeline_is_refused(context: IndexingContext) -> None:
    """Resetting an index nothing can refill would throw away recoverable vectors."""
    with pytest.raises(RebuildNotSupportedError, match="no reindexer"):
        rebuild_index("video_segment", context)


def test_a_refused_rebuild_leaves_the_index_untouched(context: IndexingContext) -> None:
    add_video(context, "vid-1", vector_id=1)
    context.registry.save("video_segment")

    with pytest.raises(RebuildNotSupportedError):
        rebuild_index("video_segment", context)

    assert context.registry.open("video_segment").size == 1


def test_a_custom_reindexer_can_be_supplied(context: IndexingContext, incoming: Path) -> None:
    """The registry is injectable so the document and video pipelines can join it."""
    index_image(write_image(incoming), context)
    seen: list[str] = []

    def fake(record: FileRecord, _context: IndexingContext, _progress: object) -> None:
        seen.append(record.id)

    result = rebuild_index("image", context, reindexers={"image": fake})

    assert len(seen) == 1
    assert result.reindexed == 1


def test_the_rebuildable_states_exclude_missing_files() -> None:
    assert "missing" not in REBUILDABLE_STATES
    assert set(REBUILDABLE_STATES) == {"indexed", "needs_reindex", "pending"}
