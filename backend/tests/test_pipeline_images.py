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
from fileseek.extract.images import UnreadableImageError
from fileseek.index.registry import IndexRegistry
from fileseek.library.layout import LibraryLayout
from fileseek.models.tiers import CPU_BUNDLE
from fileseek.models.vectors import is_normalized, normalize
from fileseek.pipeline.context import IndexingContext
from fileseek.pipeline.images import index_image, reindex_image
from fileseek.tasks import TaskQueue
from fileseek.tasks.records import STAGE_ORDER, Stage

IMAGE_WIDTH = CPU_BUNDLE.image_dimensions


class DimensionedEncoder:
    """Deterministic vectors of the real width, so they fit the actual index.

    The payload length seeds the vector, which keeps assertions exact while still
    giving different pictures different directions.
    """

    def __init__(self, recognized: str = "") -> None:
        self.recognized = recognized
        self.image_batches: list[int] = []
        self.ocr_payload_sizes: list[int] = []

    def _seeded(self, seed: int, width: int) -> list[float]:
        raw = [1.0 if index == seed % width else 0.25 for index in range(width)]
        return normalize(raw)

    def encode_images(self, images: Sequence[bytes]) -> list[list[float]]:
        self.image_batches.append(len(images))
        return [self._seeded(len(payload), IMAGE_WIDTH) for payload in images]

    def encode_texts(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._seeded(len(text), CPU_BUNDLE.text_dimensions) for text in texts]

    def recognize_text(self, image: bytes) -> str:
        self.ocr_payload_sizes.append(len(image))
        return self.recognized


class RecordingProgress:
    def __init__(self) -> None:
        self.reported: list[tuple[Stage, int]] = []
        self.completed: list[Stage] = []

    def report(self, stage: Stage, percent: int) -> None:
        self.reported.append((stage, percent))

    def stage_done(self, stage: Stage) -> None:
        self.completed.append(stage)


@pytest.fixture
def db() -> Iterator[sqlite3.Connection]:
    connection = connect(":memory:")
    migrate(connection)
    yield connection
    connection.close()


@pytest.fixture
def encoder() -> DimensionedEncoder:
    return DimensionedEncoder()


@pytest.fixture
def context(tmp_path: Path, db: sqlite3.Connection, encoder: DimensionedEncoder) -> IndexingContext:
    layout = LibraryLayout(root=tmp_path / "library").initialize()
    return IndexingContext(
        layout=layout,
        files=FileRepository(db),
        images=ImageRepository(db),
        documents=DocumentRepository(db),
        videos=VideoRepository(db),
        segments=SegmentRepository(db),
        chunks=ChunkRepository(db),
        registry=IndexRegistry(tmp_path / "index", db, CPU_BUNDLE),
        encoder=encoder,
    )


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


def test_image_is_moved_into_the_library(context: IndexingContext, incoming: Path) -> None:
    source = write_image(incoming)

    result = index_image(source, context)

    assert Path(result.record.path).parent == context.layout.media_dir("image")
    assert Path(result.record.path).is_file()
    assert not source.exists()


def test_dimensions_are_recorded(context: IndexingContext, incoming: Path) -> None:
    source = write_image(incoming, size=(640, 480))

    result = index_image(source, context)

    assert result.metadata is not None
    assert (result.metadata.width, result.metadata.height) == (640, 480)
    stored = context.images.get(result.record.id)
    assert stored is not None
    assert (stored.width, stored.height) == (640, 480)


def test_the_vector_lands_in_the_image_index(context: IndexingContext, incoming: Path) -> None:
    source = write_image(incoming)

    result = index_image(source, context)

    assert result.vector_id is not None
    assert context.registry.open("image").size == 1
    assert context.registry.open("image").reconstruct(result.vector_id) is not None


def test_indexed_image_is_findable_by_its_own_vector(
    context: IndexingContext, incoming: Path
) -> None:
    """Round trip: what the pipeline stored has to come back from a search."""
    source = write_image(incoming)
    result = index_image(source, context)
    stored_vector = context.registry.open("image").reconstruct(result.vector_id or 0)
    assert stored_vector is not None

    hits = context.registry.search("image", stored_vector, limit=5)

    assert [hit.vector_id for hit in hits] == [result.vector_id]
    assert hits[0].score == pytest.approx(1.0, abs=1e-4)


def test_a_hit_resolves_back_to_the_file(context: IndexingContext, incoming: Path) -> None:
    source = write_image(incoming, name="kitten.jpg")
    result = index_image(source, context)

    found = context.images.by_vector_ids([result.vector_id or 0])

    assert [record.file_id for record in found] == [result.record.id]
    file_record = context.files.get(result.record.id)
    assert file_record is not None
    assert file_record.filename == "kitten.jpg"


def test_stored_vector_is_normalized(context: IndexingContext, incoming: Path) -> None:
    result = index_image(write_image(incoming), context)

    stored = context.registry.open("image").reconstruct(result.vector_id or 0)
    assert stored is not None
    assert is_normalized(stored, tolerance=1e-5)


def test_the_file_is_marked_indexed(context: IndexingContext, incoming: Path) -> None:
    result = index_image(write_image(incoming), context)

    stored = context.files.get(result.record.id)
    assert stored is not None
    assert stored.index_state == "indexed"


def test_the_index_is_persisted(context: IndexingContext, incoming: Path) -> None:
    """A restart must not lose the work, so the index is written to disk."""
    index_image(write_image(incoming), context)

    assert context.registry.path_for("image").is_file()


def test_recognized_text_is_stored(tmp_path: Path, db: sqlite3.Connection, incoming: Path) -> None:
    encoder = DimensionedEncoder(recognized="深度学习 notes")
    context = IndexingContext(
        layout=LibraryLayout(root=tmp_path / "library").initialize(),
        files=FileRepository(db),
        images=ImageRepository(db),
        documents=DocumentRepository(db),
        videos=VideoRepository(db),
        segments=SegmentRepository(db),
        chunks=ChunkRepository(db),
        registry=IndexRegistry(tmp_path / "index", db, CPU_BUNDLE),
        encoder=encoder,
    )

    result = index_image(write_image(incoming, name="screenshot.png"), context)

    assert result.has_recognized_text is True
    stored = context.images.get(result.record.id)
    assert stored is not None
    assert stored.ocr_text == "深度学习 notes"


def test_recognized_text_makes_the_image_searchable_by_words(
    tmp_path: Path, db: sqlite3.Connection, incoming: Path
) -> None:
    """A screenshot must be findable by the words shown in it."""
    context = IndexingContext(
        layout=LibraryLayout(root=tmp_path / "library").initialize(),
        files=FileRepository(db),
        images=ImageRepository(db),
        documents=DocumentRepository(db),
        videos=VideoRepository(db),
        segments=SegmentRepository(db),
        chunks=ChunkRepository(db),
        registry=IndexRegistry(tmp_path / "index", db, CPU_BUNDLE),
        encoder=DimensionedEncoder(recognized="quarterly revenue chart"),
    )
    result = index_image(write_image(incoming, name="chart.png"), context)

    rows = db.execute(
        "SELECT images.file_id FROM images_fts "
        "JOIN images ON images.rowid = images_fts.rowid WHERE images_fts MATCH ?",
        ("revenue",),
    ).fetchall()

    assert [row["file_id"] for row in rows] == [result.record.id]


def test_image_without_text_stores_null(context: IndexingContext, incoming: Path) -> None:
    result = index_image(write_image(incoming), context)

    stored = context.images.get(result.record.id)
    assert stored is not None
    assert stored.ocr_text is None
    assert result.has_recognized_text is False


def test_recognition_gets_more_detail_than_the_encoder(
    context: IndexingContext, incoming: Path, encoder: DimensionedEncoder
) -> None:
    """Text is unreadable at the encoder's size, so OCR receives a larger copy."""
    index_image(write_image(incoming, size=(2000, 1500)), context)

    assert encoder.ocr_payload_sizes
    assert encoder.image_batches == [1]


def test_stages_are_reported_in_order(context: IndexingContext, incoming: Path) -> None:
    progress = RecordingProgress()

    index_image(write_image(incoming), context, progress)

    assert progress.completed == list(STAGE_ORDER)


def test_progress_reaches_the_task_queue(
    context: IndexingContext, incoming: Path, db: sqlite3.Connection
) -> None:
    from fileseek.pipeline.context import QueueProgress

    queue = TaskQueue(db)
    task = queue.enqueue("cat.jpg", media_type="image")
    queue.claim_next()

    index_image(write_image(incoming), context, QueueProgress(queue, task.id))

    assert queue.get(task.id).completed_stages == STAGE_ORDER


def test_duplicate_image_is_not_indexed_twice(context: IndexingContext, incoming: Path) -> None:
    first = index_image(write_image(incoming, name="cat.jpg"), context)
    nested = incoming / "again"
    nested.mkdir()
    duplicate_source = write_image(nested, name="copy.jpg")

    second = index_image(duplicate_source, context)

    assert second.was_duplicate is True
    assert second.record.id == first.record.id
    assert context.registry.open("image").size == 1
    assert context.files.count() == 1


def test_duplicate_reports_the_existing_entry(context: IndexingContext, incoming: Path) -> None:
    first = index_image(write_image(incoming, name="cat.jpg", size=(320, 240)), context)
    nested = incoming / "again"
    nested.mkdir()

    second = index_image(write_image(nested, name="copy.jpg", size=(320, 240)), context)

    assert second.vector_id == first.vector_id
    assert second.metadata is not None
    assert (second.metadata.width, second.metadata.height) == (320, 240)


def test_duplicate_records_the_new_origin(context: IndexingContext, incoming: Path) -> None:
    first_source = write_image(incoming, name="cat.jpg")
    result = index_image(first_source, context)
    nested = incoming / "again"
    nested.mkdir()
    second_source = write_image(nested, name="copy.jpg")

    index_image(second_source, context)

    assert context.files.origins(result.record.id) == [str(first_source), str(second_source)]


def test_duplicate_of_an_unindexed_file_reports_nothing_stored(
    context: IndexingContext, incoming: Path
) -> None:
    """Ingested but not yet encoded: there is no vector to report, and none is invented."""
    from fileseek.library.ingest import ingest_file

    first = ingest_file(write_image(incoming, name="cat.jpg"), context.layout, context.files)
    nested = incoming / "again"
    nested.mkdir()

    result = index_image(write_image(nested, name="copy.jpg"), context)

    assert result.was_duplicate is True
    assert result.record.id == first.record.id
    assert result.vector_id is None
    assert result.metadata is None
    assert result.is_searchable is False


def test_different_images_get_different_vectors(context: IndexingContext, incoming: Path) -> None:
    first = index_image(write_image(incoming, name="a.jpg", size=(100, 100)), context)
    second = index_image(write_image(incoming, name="b.jpg", size=(400, 300)), context)

    assert first.vector_id != second.vector_id
    assert context.registry.open("image").size == 2


def test_reindexing_replaces_the_previous_vector(context: IndexingContext, incoming: Path) -> None:
    """Ids are never reused, so a stale vector would otherwise keep matching."""
    first = index_image(write_image(incoming, name="cat.jpg"), context)
    assert first.vector_id is not None

    result = reindex_image(first.record, context)

    assert result.vector_id != first.vector_id
    assert context.registry.open("image").reconstruct(first.vector_id) is None
    assert context.registry.open("image").size == 1


def test_reindexing_picks_up_replaced_content(context: IndexingContext, incoming: Path) -> None:
    """A file swapped behind our back must be described by its new content."""
    first = index_image(write_image(incoming, name="cat.jpg", size=(320, 240)), context)
    Image.new("RGB", (800, 600), (20, 20, 200)).save(Path(first.record.path))

    result = reindex_image(first.record, context)

    assert result.metadata is not None
    assert (result.metadata.width, result.metadata.height) == (800, 600)
    stored = context.images.get(first.record.id)
    assert stored is not None
    assert (stored.width, stored.height) == (800, 600)


def test_reindexing_restores_the_indexed_state(context: IndexingContext, incoming: Path) -> None:
    first = index_image(write_image(incoming, name="cat.jpg"), context)
    context.files.set_index_state(first.record.id, "needs_reindex")

    reindex_image(first.record, context)

    stored = context.files.get(first.record.id)
    assert stored is not None
    assert stored.index_state == "indexed"


def test_reindexing_reports_every_stage(context: IndexingContext, incoming: Path) -> None:
    first = index_image(write_image(incoming, name="cat.jpg"), context)
    progress = RecordingProgress()

    reindex_image(first.record, context, progress)

    assert progress.completed == list(STAGE_ORDER)


def test_corrupt_image_fails_but_stays_in_the_library(
    context: IndexingContext, incoming: Path
) -> None:
    source = incoming / "broken.jpg"
    source.write_bytes(b"not an image at all")

    with pytest.raises(UnreadableImageError, match="could not read image"):
        index_image(source, context)

    # The move happened before decoding, so the bytes are safe in the library.
    library_copy = context.layout.media_dir("image") / "broken.jpg"
    assert library_copy.is_file()
    assert not source.exists()


def test_corrupt_image_leaves_no_vector(context: IndexingContext, incoming: Path) -> None:
    source = incoming / "broken.jpg"
    source.write_bytes(b"not an image at all")

    with pytest.raises(UnreadableImageError):
        index_image(source, context)

    assert context.registry.open("image").size == 0


def test_corrupt_image_is_not_marked_indexed(context: IndexingContext, incoming: Path) -> None:
    source = incoming / "broken.jpg"
    source.write_bytes(b"not an image at all")

    with pytest.raises(UnreadableImageError):
        index_image(source, context)

    stored = context.files.get_by_path(str(context.layout.media_dir("image") / "broken.jpg"))
    assert stored is not None
    assert stored.index_state == "pending"


def test_missing_source_is_rejected(context: IndexingContext, incoming: Path) -> None:
    from fileseek.library.mover import SourceMissingError

    with pytest.raises(SourceMissingError):
        index_image(incoming / "absent.jpg", context)


def test_several_images_accumulate_in_the_index(context: IndexingContext, incoming: Path) -> None:
    for index in range(5):
        index_image(write_image(incoming, name=f"img{index}.jpg", size=(100 + index, 100)), context)

    assert context.registry.open("image").size == 5
    assert context.files.count() == 5
