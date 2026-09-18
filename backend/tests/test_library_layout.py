from pathlib import Path

import pytest

from fileseek.library.layout import (
    THUMBNAIL_DIRNAME,
    LibraryLayout,
    LibraryNotWritableError,
    NameAllocationError,
)
from fileseek.library.mover import PART_SUFFIX


@pytest.fixture
def layout(tmp_path: Path) -> LibraryLayout:
    return LibraryLayout(root=tmp_path / "library").initialize()


def test_initialize_creates_every_subdirectory(tmp_path: Path) -> None:
    layout = LibraryLayout(root=tmp_path / "library").initialize()

    assert (layout.root / "documents").is_dir()
    assert (layout.root / "images").is_dir()
    assert (layout.root / "videos").is_dir()
    assert layout.thumbnail_dir.is_dir()


def test_initialize_is_idempotent(tmp_path: Path) -> None:
    root = tmp_path / "library"
    LibraryLayout(root=root).initialize()
    (root / "images" / "existing.jpg").write_bytes(b"x")

    LibraryLayout(root=root).initialize()

    assert (root / "images" / "existing.jpg").exists()


def test_thumbnail_dir_is_hidden_by_name(layout: LibraryLayout) -> None:
    assert layout.thumbnail_dir.name == THUMBNAIL_DIRNAME
    assert layout.thumbnail_dir.name.startswith(".")


def test_media_dir_per_type(layout: LibraryLayout) -> None:
    assert layout.media_dir("document") == layout.root / "documents"
    assert layout.media_dir("image") == layout.root / "images"
    assert layout.media_dir("video") == layout.root / "videos"


def test_unwritable_root_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "readonly"

    def deny(*args: object, **kwargs: object) -> None:
        raise PermissionError("access denied")

    monkeypatch.setattr(Path, "mkdir", deny)
    layout = LibraryLayout(root=root)

    with pytest.raises(LibraryNotWritableError, match="not writable"):
        layout.initialize()


def test_unwritable_root_reports_root_and_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "readonly"
    monkeypatch.setattr(
        Path, "open", lambda *a, **k: (_ for _ in ()).throw(PermissionError("no write"))
    )

    with pytest.raises(LibraryNotWritableError) as excinfo:
        LibraryLayout(root=root).verify_writable()

    assert excinfo.value.root == root
    assert "no write" in excinfo.value.reason


def test_write_probe_leaves_no_file_behind(tmp_path: Path) -> None:
    root = tmp_path / "library"
    layout = LibraryLayout(root=root)

    layout.verify_writable()

    assert list(root.iterdir()) == []


def test_allocate_path_uses_original_name_when_free(layout: LibraryLayout) -> None:
    assert layout.allocate_path("image", "cat.jpg") == layout.root / "images" / "cat.jpg"


def test_allocate_path_suffixes_on_collision(layout: LibraryLayout) -> None:
    (layout.root / "images" / "cat.jpg").write_bytes(b"first")

    allocated = layout.allocate_path("image", "cat.jpg")

    assert allocated == layout.root / "images" / "cat-2.jpg"


def test_allocate_path_keeps_counting_past_second_collision(layout: LibraryLayout) -> None:
    (layout.root / "images" / "cat.jpg").write_bytes(b"first")
    (layout.root / "images" / "cat-2.jpg").write_bytes(b"second")

    assert layout.allocate_path("image", "cat.jpg").name == "cat-3.jpg"


def test_allocate_path_does_not_overwrite_existing_file(layout: LibraryLayout) -> None:
    existing = layout.root / "images" / "cat.jpg"
    existing.write_bytes(b"original")

    layout.allocate_path("image", "cat.jpg")

    assert existing.read_bytes() == b"original"


def test_allocate_path_preserves_multi_dot_extension(layout: LibraryLayout) -> None:
    (layout.root / "videos" / "clip.final.mp4").write_bytes(b"x")

    allocated = layout.allocate_path("video", "clip.final.mp4")

    assert allocated.name == "clip.final-2.mp4"


def test_allocate_path_gives_up_after_max_attempts(
    layout: LibraryLayout, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "exists", lambda self: True)

    with pytest.raises(NameAllocationError, match="free name"):
        layout.allocate_path("image", "cat.jpg")


def test_relative_to_root(layout: LibraryLayout) -> None:
    target = layout.root / "images" / "cat.jpg"

    assert layout.relative_to_root(target) == "images/cat.jpg"


def test_thumbnail_path_is_under_thumbnail_dir(layout: LibraryLayout) -> None:
    assert layout.thumbnail_path("v1/s1.jpg") == layout.thumbnail_dir / "v1" / "s1.jpg"


def test_contains_accepts_paths_inside_library(layout: LibraryLayout) -> None:
    assert layout.contains(layout.root / "images" / "cat.jpg") is True
    assert layout.contains(layout.root) is True


def test_contains_rejects_paths_outside_library(layout: LibraryLayout, tmp_path: Path) -> None:
    assert layout.contains(tmp_path / "elsewhere.jpg") is False


def test_contains_rejects_traversal_escape(layout: LibraryLayout) -> None:
    assert layout.contains(layout.root / ".." / "secret.txt") is False


def test_initialize_skips_hidden_attribute_off_windows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import ctypes

    monkeypatch.delattr(ctypes, "windll", raising=False)

    layout = LibraryLayout(root=tmp_path / "library").initialize()

    assert layout.thumbnail_dir.is_dir()


def test_initialize_removes_leftover_part_files(tmp_path: Path) -> None:
    root = tmp_path / "library"
    LibraryLayout(root=root).initialize()
    orphan = root / "videos" / f"interrupted.mp4{PART_SUFFIX}"
    orphan.write_bytes(b"partial")
    keeper = root / "videos" / "finished.mp4"
    keeper.write_bytes(b"whole")

    LibraryLayout(root=root).initialize()

    assert not orphan.exists()
    assert keeper.read_bytes() == b"whole"


def test_initialize_sweeps_every_media_subdirectory(tmp_path: Path) -> None:
    root = tmp_path / "library"
    layout = LibraryLayout(root=root).initialize()
    orphans = [
        layout.media_dir("document") / f"report.pdf{PART_SUFFIX}",
        layout.media_dir("image") / f"cat.jpg{PART_SUFFIX}",
        layout.media_dir("video") / f"clip.mp4{PART_SUFFIX}",
        layout.thumbnail_dir / f"v1.jpg{PART_SUFFIX}",
    ]
    for orphan in orphans:
        orphan.write_bytes(b"partial")

    removed = LibraryLayout(root=root).cleanup_interrupted_moves()

    assert sorted(removed) == sorted(orphans)
    assert not any(orphan.exists() for orphan in orphans)


def test_cleanup_reports_nothing_on_a_clean_library(layout: LibraryLayout) -> None:
    assert layout.cleanup_interrupted_moves() == []


def test_contains_handles_unresolvable_path(
    layout: LibraryLayout, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        Path, "resolve", lambda self, strict=False: (_ for _ in ()).throw(OSError("bad path"))
    )

    assert layout.contains(layout.root / "images" / "cat.jpg") is False
