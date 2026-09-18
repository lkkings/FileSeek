import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from fileseek.db import FileRepository, connect, migrate
from fileseek.library.ingest import UnsupportedMediaError, ingest_file
from fileseek.library.layout import LibraryLayout
from fileseek.library.mover import SourceMissingError


@pytest.fixture
def db() -> Iterator[sqlite3.Connection]:
    connection = connect(":memory:")
    migrate(connection)
    yield connection
    connection.close()


@pytest.fixture
def files(db: sqlite3.Connection) -> FileRepository:
    return FileRepository(db)


@pytest.fixture
def layout(tmp_path: Path) -> LibraryLayout:
    return LibraryLayout(root=tmp_path / "library").initialize()


@pytest.fixture
def incoming(tmp_path: Path) -> Path:
    directory = tmp_path / "downloads"
    directory.mkdir()
    return directory


def write(directory: Path, name: str, payload: bytes = b"payload") -> Path:
    path = directory / name
    path.write_bytes(payload)
    return path


def test_image_lands_in_image_directory(
    layout: LibraryLayout, files: FileRepository, incoming: Path
) -> None:
    source = write(incoming, "cat.jpg")

    outcome = ingest_file(source, layout, files)

    assert outcome.was_duplicate is False
    assert Path(outcome.record.path) == layout.root / "images" / "cat.jpg"
    assert Path(outcome.record.path).is_file()


def test_source_no_longer_exists_after_ingest(
    layout: LibraryLayout, files: FileRepository, incoming: Path
) -> None:
    source = write(incoming, "cat.jpg")

    ingest_file(source, layout, files)

    assert not source.exists()


def test_original_path_is_recorded(
    layout: LibraryLayout, files: FileRepository, incoming: Path
) -> None:
    source = write(incoming, "cat.jpg")

    outcome = ingest_file(source, layout, files)

    assert files.origins(outcome.record.id) == [str(source)]


def test_document_and_video_route_to_their_directories(
    layout: LibraryLayout, files: FileRepository, incoming: Path
) -> None:
    doc = ingest_file(write(incoming, "paper.pdf", b"doc"), layout, files)
    video = ingest_file(write(incoming, "clip.mp4", b"vid"), layout, files)

    assert Path(doc.record.path).parent == layout.root / "documents"
    assert Path(video.record.path).parent == layout.root / "videos"


def test_record_captures_size_hash_and_type(
    layout: LibraryLayout, files: FileRepository, incoming: Path
) -> None:
    source = write(incoming, "cat.jpg", b"12345")

    record = ingest_file(source, layout, files).record

    assert record.size == 5
    assert record.media_type == "image"
    assert len(record.content_hash) == 64
    assert record.index_state == "pending"


def test_record_is_persisted_and_findable(
    layout: LibraryLayout, files: FileRepository, incoming: Path
) -> None:
    source = write(incoming, "cat.jpg")

    record = ingest_file(source, layout, files).record

    assert files.get(record.id) == record
    assert files.get_by_content_hash(record.content_hash) == record


def test_record_keeps_source_timestamps(
    layout: LibraryLayout, files: FileRepository, incoming: Path
) -> None:
    source = write(incoming, "cat.jpg")

    record = ingest_file(source, layout, files).record

    assert record.created_at is not None
    assert record.modified_at is not None


def test_duplicate_content_does_not_create_second_copy(
    layout: LibraryLayout, files: FileRepository, incoming: Path
) -> None:
    first = ingest_file(write(incoming, "cat.jpg", b"same bytes"), layout, files)
    second_source = write(incoming, "cat-copy.jpg", b"same bytes")

    second = ingest_file(second_source, layout, files)

    assert second.was_duplicate is True
    assert second.record.id == first.record.id
    assert files.count() == 1
    assert len(list((layout.root / "images").iterdir())) == 1


def test_duplicate_leaves_the_submitted_file_in_place(
    layout: LibraryLayout, files: FileRepository, incoming: Path
) -> None:
    ingest_file(write(incoming, "cat.jpg", b"same bytes"), layout, files)
    second_source = write(incoming, "cat-copy.jpg", b"same bytes")

    ingest_file(second_source, layout, files)

    assert second_source.exists()


def test_duplicate_appends_the_new_origin(
    layout: LibraryLayout, files: FileRepository, incoming: Path
) -> None:
    first_source = write(incoming, "cat.jpg", b"same bytes")
    outcome = ingest_file(first_source, layout, files)
    second_source = write(incoming, "cat-copy.jpg", b"same bytes")

    ingest_file(second_source, layout, files)

    assert files.origins(outcome.record.id) == [str(first_source), str(second_source)]


def test_same_name_different_content_both_kept(
    layout: LibraryLayout, files: FileRepository, incoming: Path
) -> None:
    first = ingest_file(write(incoming, "cat.jpg", b"first"), layout, files)
    nested = incoming / "other"
    nested.mkdir()
    second = ingest_file(write(nested, "cat.jpg", b"second"), layout, files)

    assert first.record.id != second.record.id
    assert Path(first.record.path).name == "cat.jpg"
    assert Path(second.record.path).name == "cat-2.jpg"
    assert files.count() == 2


def test_existing_library_file_is_not_overwritten(
    layout: LibraryLayout, files: FileRepository, incoming: Path
) -> None:
    ingest_file(write(incoming, "cat.jpg", b"first"), layout, files)
    nested = incoming / "other"
    nested.mkdir()

    ingest_file(write(nested, "cat.jpg", b"second"), layout, files)

    assert (layout.root / "images" / "cat.jpg").read_bytes() == b"first"


def test_unsupported_type_is_rejected(
    layout: LibraryLayout, files: FileRepository, incoming: Path
) -> None:
    source = write(incoming, "setup.exe")

    with pytest.raises(UnsupportedMediaError, match="unsupported"):
        ingest_file(source, layout, files)

    assert source.exists()
    assert files.count() == 0


def test_missing_source_is_rejected(
    layout: LibraryLayout, files: FileRepository, incoming: Path
) -> None:
    with pytest.raises(SourceMissingError):
        ingest_file(incoming / "ghost.jpg", layout, files)


def test_explicit_media_type_overrides_extension(
    layout: LibraryLayout, files: FileRepository, incoming: Path
) -> None:
    source = write(incoming, "scan.jpg")

    outcome = ingest_file(source, layout, files, media_type="document")

    assert Path(outcome.record.path).parent == layout.root / "documents"


def test_move_failure_keeps_source_and_writes_no_record(
    layout: LibraryLayout,
    files: FileRepository,
    incoming: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = write(incoming, "cat.jpg")
    monkeypatch.setattr(
        Path, "rename", lambda self, target: (_ for _ in ()).throw(PermissionError("denied"))
    )

    with pytest.raises(PermissionError):
        ingest_file(source, layout, files)

    monkeypatch.undo()
    assert source.exists()
    assert files.count() == 0


def test_timestamps_unavailable_are_tolerated(
    layout: LibraryLayout,
    files: FileRepository,
    incoming: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = write(incoming, "cat.jpg")
    real_stat = Path.stat
    calls = {"n": 0}

    def flaky_stat(self: Path, **kwargs: object):  # type: ignore[no-untyped-def]
        if self == source:
            calls["n"] += 1
            if calls["n"] == 2:
                raise OSError("stat failed")
        return real_stat(self, **kwargs)

    monkeypatch.setattr(Path, "stat", flaky_stat)

    record = ingest_file(source, layout, files).record

    assert record.created_at is None
    assert record.modified_at is None
