from pathlib import Path

import pytest

from fileseek.media_types import (
    DOCUMENT_EXTENSIONS,
    IMAGE_EXTENSIONS,
    SUPPORTED_EXTENSIONS,
    VIDEO_EXTENSIONS,
    filter_supported,
    is_supported,
    manifest,
    media_type_for,
)


@pytest.mark.parametrize("extension", sorted(DOCUMENT_EXTENSIONS))
def test_document_extensions_map_to_document(extension: str) -> None:
    assert media_type_for(f"paper{extension}") == "document"


@pytest.mark.parametrize("extension", sorted(IMAGE_EXTENSIONS))
def test_image_extensions_map_to_image(extension: str) -> None:
    assert media_type_for(f"photo{extension}") == "image"


@pytest.mark.parametrize("extension", sorted(VIDEO_EXTENSIONS))
def test_video_extensions_map_to_video(extension: str) -> None:
    assert media_type_for(f"clip{extension}") == "video"


def test_spec_required_extensions_are_covered() -> None:
    assert {".pdf", ".docx", ".txt", ".md"} <= DOCUMENT_EXTENSIONS
    assert {".jpg", ".png", ".webp", ".gif", ".bmp"} <= IMAGE_EXTENSIONS
    assert {".mp4", ".mov", ".mkv", ".avi", ".webm"} <= VIDEO_EXTENSIONS


def test_extension_matching_ignores_case() -> None:
    assert media_type_for("PHOTO.JPG") == "image"
    assert media_type_for(Path("Paper.PDF")) == "document"


def test_unsupported_extension_has_no_type() -> None:
    assert media_type_for("installer.exe") is None
    assert is_supported("installer.exe") is False


def test_file_without_extension_is_unsupported() -> None:
    assert media_type_for("README") is None


def test_supported_extensions_is_the_union() -> None:
    assert SUPPORTED_EXTENSIONS == DOCUMENT_EXTENSIONS | IMAGE_EXTENSIONS | VIDEO_EXTENSIONS


def test_media_types_do_not_overlap() -> None:
    assert not DOCUMENT_EXTENSIONS & IMAGE_EXTENSIONS
    assert not IMAGE_EXTENSIONS & VIDEO_EXTENSIONS
    assert not DOCUMENT_EXTENSIONS & VIDEO_EXTENSIONS


def test_mixed_selection_keeps_only_supported() -> None:
    selection = ["a.jpg", "b.png", "c.gif", "movie.mp4", "setup.exe"]

    kept = filter_supported(selection)

    assert [path.name for path in kept] == ["a.jpg", "b.png", "c.gif", "movie.mp4"]


def test_selection_without_supported_files_is_empty() -> None:
    assert filter_supported(["setup.exe", "notes.xyz"]) == []


def test_manifest_lists_every_extension_as_json() -> None:
    import json

    parsed = json.loads(manifest())

    assert set(parsed) == {"document", "image", "video"}
    assert sorted(IMAGE_EXTENSIONS) == parsed["image"]
