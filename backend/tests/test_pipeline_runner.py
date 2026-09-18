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
from fileseek.index.registry import IndexRegistry
from fileseek.library.ingest import ingest_file
from fileseek.library.layout import LibraryLayout
from fileseek.models.tiers import CPU_BUNDLE
from fileseek.models.vectors import normalize
from fileseek.pipeline.context import IndexingContext, ProgressReporter
from fileseek.pipeline.runner import IndexedResult, run_task
from fileseek.tasks import STAGE_ORDER, TaskQueue

from doc_fixtures import write_encrypted_pdf, write_pdf

IMAGE_WIDTH = CPU_BUNDLE.image_dimensions


class DimensionedEncoder:
    """Deterministic vectors of the real width, so they fit the actual index."""

    def _seeded(self, seed: int, width: int) -> list[float]:
        raw = [1.0 if index == seed % width else 0.25 for index in range(width)]
        return normalize(raw)

    def encode_images(self, images: Sequence[bytes]) -> list[list[float]]:
        return [self._seeded(len(payload), IMAGE_WIDTH) for payload in images]

    def encode_texts(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._seeded(len(text), CPU_BUNDLE.text_dimensions) for text in texts]

    def recognize_text(self, image: bytes) -> str:  # noqa: ARG002 - not under test here
        return ""


@pytest.fixture
def db() -> Iterator[sqlite3.Connection]:
    connection = connect(":memory:")
    migrate(connection)
    yield connection
    connection.close()


@pytest.fixture
def context(tmp_path: Path, db: sqlite3.Connection) -> IndexingContext:
    return IndexingContext(
        layout=LibraryLayout(root=tmp_path / "library").initialize(),
        files=FileRepository(db),
        images=ImageRepository(db),
        documents=DocumentRepository(db),
        videos=VideoRepository(db),
        segments=SegmentRepository(db),
        chunks=ChunkRepository(db),
        registry=IndexRegistry(tmp_path / "index", db, CPU_BUNDLE),
        encoder=DimensionedEncoder(),
    )


@pytest.fixture
def queue(db: sqlite3.Connection) -> TaskQueue:
    return TaskQueue(db)


@pytest.fixture
def incoming(tmp_path: Path) -> Path:
    directory = tmp_path / "downloads"
    directory.mkdir()
    return directory


def write_image(directory: Path, name: str = "cat.jpg") -> Path:
    path = directory / name
    Image.new("RGB", (320, 240), (220, 30, 30)).save(path)
    return path


def write_corrupt_image(directory: Path, name: str = "broken.jpg") -> Path:
    path = directory / name
    path.write_bytes(b"not an image at all")
    return path


def claim(queue: TaskQueue, source: Path, media_type: str | None = "image"):  # type: ignore[no-untyped-def]
    queue.enqueue(str(source), media_type=media_type)
    claimed = queue.claim_next()
    assert claimed is not None
    return claimed


# --- the happy path, so the failure cases mean something ---------------------


def test_a_good_image_completes_its_task(
    context: IndexingContext, queue: TaskQueue, incoming: Path
) -> None:
    task = claim(queue, write_image(incoming))

    outcome = run_task(task, queue, context)

    assert outcome.succeeded
    assert queue.get(task.id).status == "completed"


def test_a_completed_task_points_at_the_indexed_file(
    context: IndexingContext, queue: TaskQueue, incoming: Path
) -> None:
    task = claim(queue, write_image(incoming))

    outcome = run_task(task, queue, context)

    assert outcome.file_id is not None
    assert queue.get(task.id).file_id == outcome.file_id
    stored = context.files.get(outcome.file_id)
    assert stored is not None
    assert stored.index_state == "indexed"


def test_a_completed_task_reports_full_progress(
    context: IndexingContext, queue: TaskQueue, incoming: Path
) -> None:
    task = claim(queue, write_image(incoming))

    run_task(task, queue, context)

    assert queue.get(task.id).progress == 100


def test_the_stages_reach_the_task(
    context: IndexingContext, queue: TaskQueue, incoming: Path
) -> None:
    """Stage records are what let a retry skip work already done."""
    task = claim(queue, write_image(incoming))

    run_task(task, queue, context)

    assert queue.get(task.id).completed_stages == STAGE_ORDER


# --- 7.4: an undecodable image ----------------------------------------------


def test_a_corrupt_image_fails_its_task(
    context: IndexingContext, queue: TaskQueue, incoming: Path
) -> None:
    task = claim(queue, write_corrupt_image(incoming))

    outcome = run_task(task, queue, context)

    assert not outcome.succeeded
    assert queue.get(task.id).status == "failed"


def test_a_corrupt_image_records_why_it_failed(
    context: IndexingContext, queue: TaskQueue, incoming: Path
) -> None:
    task = claim(queue, write_corrupt_image(incoming))

    run_task(task, queue, context)

    message = queue.get(task.id).error_message
    assert message is not None
    assert "broken.jpg" in message


def test_the_failure_reason_is_reported_to_the_caller(
    context: IndexingContext, queue: TaskQueue, incoming: Path
) -> None:
    task = claim(queue, write_corrupt_image(incoming))

    outcome = run_task(task, queue, context)

    assert outcome.error is not None
    assert "broken.jpg" in outcome.describe()


def test_a_corrupt_image_stays_in_the_library(
    context: IndexingContext, queue: TaskQueue, incoming: Path
) -> None:
    """The move happens before decoding, so a failure must not lose the bytes."""
    source = write_corrupt_image(incoming)
    task = claim(queue, source)

    run_task(task, queue, context)

    assert (context.layout.media_dir("image") / "broken.jpg").is_file()
    assert not source.exists()


def test_a_corrupt_image_keeps_its_file_record(
    context: IndexingContext, queue: TaskQueue, incoming: Path
) -> None:
    task = claim(queue, write_corrupt_image(incoming))

    run_task(task, queue, context)

    stored = context.files.get_by_path(str(context.layout.media_dir("image") / "broken.jpg"))
    assert stored is not None
    assert stored.index_state == "pending"


def test_a_corrupt_image_leaves_no_vector(
    context: IndexingContext, queue: TaskQueue, incoming: Path
) -> None:
    task = claim(queue, write_corrupt_image(incoming))

    run_task(task, queue, context)

    assert context.registry.open("image").size == 0


def test_a_failed_task_does_not_raise(
    context: IndexingContext, queue: TaskQueue, incoming: Path
) -> None:
    """An unhandled traceback would strand the task in processing."""
    task = claim(queue, write_corrupt_image(incoming))

    run_task(task, queue, context)

    assert queue.get(task.id).status != "processing"


def test_a_failed_task_can_be_retried(
    context: IndexingContext, queue: TaskQueue, incoming: Path
) -> None:
    task = claim(queue, write_corrupt_image(incoming))
    run_task(task, queue, context)

    retried = queue.retry(task.id)

    assert retried.status == "queued"
    assert retried.error_message is None


def test_one_failure_does_not_block_the_next_task(
    context: IndexingContext, queue: TaskQueue, incoming: Path
) -> None:
    broken = claim(queue, write_corrupt_image(incoming))
    run_task(broken, queue, context)

    good = claim(queue, write_image(incoming))
    outcome = run_task(good, queue, context)

    assert outcome.succeeded


# --- other bad input --------------------------------------------------------


def test_a_missing_source_fails_with_a_reason(
    context: IndexingContext, queue: TaskQueue, incoming: Path
) -> None:
    task = claim(queue, incoming / "absent.jpg")

    outcome = run_task(task, queue, context)

    assert not outcome.succeeded
    assert "absent.jpg" in (queue.get(task.id).error_message or "")


def test_an_unsupported_type_fails_with_a_readable_reason(
    context: IndexingContext, queue: TaskQueue, incoming: Path
) -> None:
    archive = incoming / "bundle.zip"
    archive.write_bytes(b"PK\x03\x04")
    task = claim(queue, archive, media_type=None)

    outcome = run_task(task, queue, context)

    assert "unsupported file type" in (outcome.error or "")
    assert queue.get(task.id).status == "failed"


def test_a_kind_without_a_pipeline_fails_rather_than_vanishing(
    context: IndexingContext, queue: TaskQueue, incoming: Path
) -> None:
    """Video has no pipeline yet; its tasks must say so rather than disappear."""
    clip = incoming / "holiday.mp4"
    clip.write_bytes(b"\x00\x00\x00\x18ftypmp42")
    task = claim(queue, clip, media_type="video")

    outcome = run_task(task, queue, context)

    assert not outcome.succeeded
    assert queue.get(task.id).status == "failed"


# --- dispatch ---------------------------------------------------------------


def test_the_media_type_is_inferred_from_the_path_when_absent(
    context: IndexingContext, queue: TaskQueue, incoming: Path
) -> None:
    task = claim(queue, write_image(incoming), media_type=None)

    assert run_task(task, queue, context).succeeded


def test_a_custom_handler_can_be_supplied(
    context: IndexingContext, queue: TaskQueue, incoming: Path
) -> None:
    """Injectable so the document and video pipelines can join the table."""
    seen: list[Path] = []

    def fake(source: Path, _context: IndexingContext, _progress: ProgressReporter) -> IndexedResult:
        seen.append(source)
        return ingest_file(source, _context.layout, _context.files, media_type="image")

    source = write_image(incoming)
    task = claim(queue, source)

    outcome = run_task(task, queue, context, handlers={"image": fake})

    assert seen == [source]
    assert outcome.succeeded


def test_an_unexpected_error_is_not_swallowed(
    context: IndexingContext, queue: TaskQueue, incoming: Path
) -> None:
    """A bug in a pipeline should surface, not be filed as bad user input."""

    def explode(
        source: Path, _context: IndexingContext, _progress: ProgressReporter
    ) -> IndexedResult:
        raise KeyboardInterrupt

    task = claim(queue, write_image(incoming))

    with pytest.raises(KeyboardInterrupt):
        run_task(task, queue, context, handlers={"image": explode})


def test_the_outcome_describes_a_success(
    context: IndexingContext, queue: TaskQueue, incoming: Path
) -> None:
    task = claim(queue, write_image(incoming))

    assert "indexed cat.jpg" in run_task(task, queue, context).describe()


# --- 8.5: a document that cannot be parsed fails its task -------------------


def test_a_good_document_completes_its_task(
    context: IndexingContext, queue: TaskQueue, incoming: Path
) -> None:
    source = write_pdf(incoming / "paper.pdf", ["Retrieval methods for search" * 8])
    task = claim(queue, source, media_type="document")

    outcome = run_task(task, queue, context)

    assert outcome.succeeded
    assert queue.get(task.id).status == "completed"


def test_a_corrupt_document_fails_its_task_with_a_reason(
    context: IndexingContext, queue: TaskQueue, incoming: Path
) -> None:
    source = incoming / "broken.pdf"
    source.write_bytes(b"%PDF-1.4 then garbage")
    task = claim(queue, source, media_type="document")

    outcome = run_task(task, queue, context)

    assert not outcome.succeeded
    failed = queue.get(task.id)
    assert failed.status == "failed"
    assert "broken.pdf" in (failed.error_message or "")


def test_an_encrypted_document_fails_its_task_with_a_reason(
    context: IndexingContext, queue: TaskQueue, incoming: Path
) -> None:
    source = write_encrypted_pdf(incoming / "locked.pdf", ["Confidential"])
    task = claim(queue, source, media_type="document")

    run_task(task, queue, context)

    failed = queue.get(task.id)
    assert failed.status == "failed"
    assert "password protected" in (failed.error_message or "")


def test_a_failed_document_stays_in_the_library(
    context: IndexingContext, queue: TaskQueue, incoming: Path
) -> None:
    source = write_encrypted_pdf(incoming / "locked.pdf", ["Confidential"])
    task = claim(queue, source, media_type="document")

    run_task(task, queue, context)

    assert (context.layout.media_dir("document") / "locked.pdf").is_file()
    assert not source.exists()


def test_a_scan_with_no_text_completes_rather_than_failing(
    context: IndexingContext, queue: TaskQueue, incoming: Path
) -> None:
    """No readable text is a valid outcome: the file is findable by name."""
    source = write_pdf(incoming / "blank.pdf", ["", ""])
    task = claim(queue, source, media_type="document")

    outcome = run_task(task, queue, context)

    assert outcome.succeeded
    assert queue.get(task.id).status == "completed"
