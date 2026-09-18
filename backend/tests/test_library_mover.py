import hashlib
from pathlib import Path

import pytest

from fileseek.library import mover
from fileseek.library.mover import (
    PART_SUFFIX,
    SourceMissingError,
    VerificationFailedError,
    cleanup_orphan_parts,
    move_into_library,
)

PAYLOAD = b"content that will be moved into the library"
DIGEST = hashlib.sha256(PAYLOAD).hexdigest()


@pytest.fixture
def force_cross_volume(monkeypatch: pytest.MonkeyPatch) -> None:
    """tmp_path is a single volume, so the cross-volume branch must be forced."""
    monkeypatch.setattr(mover, "_same_volume", lambda source, destination_dir: False)


@pytest.fixture
def source(tmp_path: Path) -> Path:
    path = tmp_path / "incoming" / "clip.mp4"
    path.parent.mkdir(parents=True)
    path.write_bytes(PAYLOAD)
    return path


def test_same_volume_move_uses_rename(source: Path, tmp_path: Path) -> None:
    destination = tmp_path / "library" / "videos" / "clip.mp4"

    result = move_into_library(source, destination)

    assert result.used_rename is True
    assert not source.exists()
    assert destination.read_bytes() == PAYLOAD


def test_same_volume_move_reports_hash_and_size(source: Path, tmp_path: Path) -> None:
    result = move_into_library(source, tmp_path / "library" / "videos" / "clip.mp4")

    assert result.content_hash == DIGEST
    assert result.size == len(PAYLOAD)


def test_same_volume_move_reuses_known_hash(source: Path, tmp_path: Path) -> None:
    result = move_into_library(
        source, tmp_path / "library" / "videos" / "clip.mp4", known_hash="precomputed"
    )

    assert result.content_hash == "precomputed"


def test_move_creates_missing_destination_directory(source: Path, tmp_path: Path) -> None:
    destination = tmp_path / "library" / "deeper" / "videos" / "clip.mp4"

    move_into_library(source, destination)

    assert destination.is_file()


def test_missing_source_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(SourceMissingError, match="does not exist"):
        move_into_library(tmp_path / "ghost.mp4", tmp_path / "library" / "videos" / "ghost.mp4")


def test_directory_source_is_rejected(tmp_path: Path) -> None:
    directory = tmp_path / "a-directory"
    directory.mkdir()

    with pytest.raises(SourceMissingError):
        move_into_library(directory, tmp_path / "library" / "videos" / "x.mp4")


@pytest.mark.usefixtures("force_cross_volume")
def test_cross_volume_move_copies_verifies_and_deletes(source: Path, tmp_path: Path) -> None:
    destination = tmp_path / "library" / "videos" / "clip.mp4"

    result = move_into_library(source, destination)

    assert result.used_rename is False
    assert not source.exists()
    assert destination.read_bytes() == PAYLOAD
    assert result.content_hash == DIGEST
    assert result.size == len(PAYLOAD)


@pytest.mark.usefixtures("force_cross_volume")
def test_cross_volume_move_leaves_no_part_file(source: Path, tmp_path: Path) -> None:
    destination = tmp_path / "library" / "videos" / "clip.mp4"

    move_into_library(source, destination)

    assert list(destination.parent.glob(f"*{PART_SUFFIX}")) == []


@pytest.mark.usefixtures("force_cross_volume")
def test_cross_volume_move_handles_small_chunks(source: Path, tmp_path: Path) -> None:
    destination = tmp_path / "library" / "videos" / "clip.mp4"

    result = move_into_library(source, destination, chunk_size=3)

    assert destination.read_bytes() == PAYLOAD
    assert result.content_hash == DIGEST


@pytest.mark.usefixtures("force_cross_volume")
def test_verification_failure_preserves_source_and_cleans_part(
    source: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "library" / "videos" / "clip.mp4"
    # Corrupt what lands on disk so the re-read digest cannot match.
    real_open = Path.open

    def corrupting_open(self: Path, mode: str = "r", *args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        handle = real_open(self, mode, *args, **kwargs)
        if "w" in mode and self.name.endswith(PART_SUFFIX):
            original_write = handle.write

            def bad_write(data: bytes) -> int:
                return original_write(bytes(len(data)))

            handle.write = bad_write  # type: ignore[method-assign]
        return handle

    monkeypatch.setattr(Path, "open", corrupting_open)

    with pytest.raises(VerificationFailedError, match="digest mismatch"):
        move_into_library(source, destination)

    monkeypatch.undo()
    assert source.read_bytes() == PAYLOAD
    assert not destination.exists()
    assert list(destination.parent.glob(f"*{PART_SUFFIX}")) == []


@pytest.mark.usefixtures("force_cross_volume")
def test_size_mismatch_is_reported(
    source: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "library" / "videos" / "clip.mp4"
    monkeypatch.setattr(mover, "_file_size", lambda path: 999_999)

    with pytest.raises(VerificationFailedError, match="does not match"):
        move_into_library(source, destination)

    assert source.read_bytes() == PAYLOAD


@pytest.mark.usefixtures("force_cross_volume")
def test_copy_failure_midway_preserves_source(
    source: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "library" / "videos" / "clip.mp4"

    def explode(path: Path) -> int:
        raise OSError("disk full")

    monkeypatch.setattr(mover, "_file_size", explode)

    with pytest.raises(OSError, match="disk full"):
        move_into_library(source, destination)

    assert source.read_bytes() == PAYLOAD
    assert list(destination.parent.glob(f"*{PART_SUFFIX}")) == []


def test_unwritable_destination_preserves_source(
    source: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "library" / "videos" / "clip.mp4"
    monkeypatch.setattr(
        Path, "rename", lambda self, target: (_ for _ in ()).throw(PermissionError("denied"))
    )

    with pytest.raises(PermissionError):
        move_into_library(source, destination)

    assert source.read_bytes() == PAYLOAD


def test_same_volume_detection_falls_back_to_false_on_error(
    source: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        Path, "stat", lambda self, **kwargs: (_ for _ in ()).throw(OSError("stat failed"))
    )

    assert mover._same_volume(source, source.parent) is False


def test_cleanup_removes_orphan_part_files(tmp_path: Path) -> None:
    library = tmp_path / "library" / "videos"
    library.mkdir(parents=True)
    orphan = library / f"interrupted.mp4{PART_SUFFIX}"
    orphan.write_bytes(b"partial")
    keeper = library / "finished.mp4"
    keeper.write_bytes(b"whole")

    removed = cleanup_orphan_parts(tmp_path / "library")

    assert removed == [orphan]
    assert not orphan.exists()
    assert keeper.exists()


def test_cleanup_searches_nested_directories(tmp_path: Path) -> None:
    nested = tmp_path / "library" / "videos" / "sub"
    nested.mkdir(parents=True)
    orphan = nested / f"deep.mp4{PART_SUFFIX}"
    orphan.write_bytes(b"partial")

    removed = cleanup_orphan_parts(tmp_path / "library")

    assert removed == [orphan]


def test_cleanup_ignores_missing_directory(tmp_path: Path) -> None:
    assert cleanup_orphan_parts(tmp_path / "nowhere") == []


def test_cleanup_spans_several_directories(tmp_path: Path) -> None:
    first = tmp_path / "one"
    second = tmp_path / "two"
    first.mkdir()
    second.mkdir()
    (first / f"a{PART_SUFFIX}").write_bytes(b"x")
    (second / f"b{PART_SUFFIX}").write_bytes(b"y")

    removed = cleanup_orphan_parts(first, second)

    assert len(removed) == 2


def test_cleanup_skips_undeletable_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    library = tmp_path / "library"
    library.mkdir()
    (library / f"locked{PART_SUFFIX}").write_bytes(b"x")
    monkeypatch.setattr(
        Path, "unlink", lambda self, missing_ok=False: (_ for _ in ()).throw(OSError("locked"))
    )

    assert cleanup_orphan_parts(library) == []


def test_cleanup_ignores_part_named_directory(tmp_path: Path) -> None:
    library = tmp_path / "library"
    decoy = library / f"notafile{PART_SUFFIX}"
    decoy.mkdir(parents=True)

    assert cleanup_orphan_parts(library) == []
    assert decoy.is_dir()
