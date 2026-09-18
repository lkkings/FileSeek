import io
from pathlib import Path

import pytest
from PIL import Image

from fileseek.extract.images import (
    DEFAULT_MAX_EDGE,
    UnreadableImageError,
    encode_for_worker,
    load_for_encoding,
    read_metadata,
)


def write_image(
    path: Path,
    size: tuple[int, int] = (200, 120),
    colour: tuple[int, int, int] = (220, 30, 30),
    image_format: str = "PNG",
    mode: str = "RGB",
) -> Path:
    image = Image.new(mode, size, colour if mode == "RGB" else 128)
    image.save(path, format=image_format)
    return path


def test_metadata_reports_dimensions(tmp_path: Path) -> None:
    target = write_image(tmp_path / "cat.png", size=(320, 240))

    metadata = read_metadata(target)

    assert (metadata.width, metadata.height) == (320, 240)
    assert metadata.pixels == 320 * 240
    assert metadata.image_format == "png"


@pytest.mark.parametrize(
    ("suffix", "image_format"),
    [(".jpg", "JPEG"), (".png", "PNG"), (".webp", "WEBP"), (".bmp", "BMP"), (".gif", "GIF")],
)
def test_every_supported_format_is_readable(tmp_path: Path, suffix: str, image_format: str) -> None:
    target = write_image(tmp_path / f"photo{suffix}", image_format=image_format)

    assert read_metadata(target).width == 200


def test_missing_file_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(UnreadableImageError, match="does not exist"):
        read_metadata(tmp_path / "absent.jpg")


def test_corrupt_image_is_rejected(tmp_path: Path) -> None:
    target = tmp_path / "broken.png"
    target.write_bytes(b"\x89PNG\r\n\x1a\n truncated garbage")

    with pytest.raises(UnreadableImageError) as excinfo:
        read_metadata(target)

    assert excinfo.value.path == target


def test_text_file_named_as_image_is_rejected(tmp_path: Path) -> None:
    target = tmp_path / "notreally.jpg"
    target.write_text("just text", encoding="utf-8")

    with pytest.raises(UnreadableImageError):
        read_metadata(target)


def test_encoding_produces_loadable_png_bytes(tmp_path: Path) -> None:
    target = write_image(tmp_path / "cat.png", size=(100, 80))

    payload = load_for_encoding(target)

    with Image.open(io.BytesIO(payload)) as decoded:
        assert decoded.format == "PNG"
        assert decoded.size == (100, 80)


def test_large_image_is_downscaled(tmp_path: Path) -> None:
    """Full-resolution pixels would cross the process boundary for nothing."""
    target = write_image(tmp_path / "huge.png", size=(4000, 2000))

    payload = load_for_encoding(target, max_edge=512)

    with Image.open(io.BytesIO(payload)) as decoded:
        assert max(decoded.size) == 512
        assert decoded.size == (512, 256)


def test_small_image_is_not_upscaled(tmp_path: Path) -> None:
    target = write_image(tmp_path / "small.png", size=(64, 48))

    payload = load_for_encoding(target, max_edge=512)

    with Image.open(io.BytesIO(payload)) as decoded:
        assert decoded.size == (64, 48)


def test_aspect_ratio_is_preserved(tmp_path: Path) -> None:
    target = write_image(tmp_path / "wide.png", size=(1600, 400))

    payload = load_for_encoding(target, max_edge=400)

    with Image.open(io.BytesIO(payload)) as decoded:
        assert decoded.size == (400, 100)


def test_extreme_aspect_ratio_keeps_at_least_one_pixel(tmp_path: Path) -> None:
    target = write_image(tmp_path / "sliver.png", size=(2000, 3))

    payload = load_for_encoding(target, max_edge=100)

    with Image.open(io.BytesIO(payload)) as decoded:
        assert decoded.size[1] >= 1


def test_greyscale_image_becomes_rgb(tmp_path: Path) -> None:
    """The encoder expects three channels regardless of the source mode."""
    target = write_image(tmp_path / "grey.png", mode="L")

    payload = load_for_encoding(target)

    with Image.open(io.BytesIO(payload)) as decoded:
        assert decoded.mode == "RGB"


def test_transparent_image_becomes_rgb(tmp_path: Path) -> None:
    target = tmp_path / "alpha.png"
    Image.new("RGBA", (80, 80), (10, 200, 10, 128)).save(target)

    payload = load_for_encoding(target)

    with Image.open(io.BytesIO(payload)) as decoded:
        assert decoded.mode == "RGB"


def test_palette_image_becomes_rgb(tmp_path: Path) -> None:
    target = tmp_path / "palette.gif"
    Image.new("P", (60, 60)).save(target)

    payload = load_for_encoding(target)

    with Image.open(io.BytesIO(payload)) as decoded:
        assert decoded.mode == "RGB"


def test_default_max_edge_is_applied(tmp_path: Path) -> None:
    target = write_image(tmp_path / "big.png", size=(DEFAULT_MAX_EDGE * 2, DEFAULT_MAX_EDGE * 2))

    payload = load_for_encoding(target)

    with Image.open(io.BytesIO(payload)) as decoded:
        assert max(decoded.size) == DEFAULT_MAX_EDGE


def test_encoding_a_missing_file_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(UnreadableImageError, match="does not exist"):
        load_for_encoding(tmp_path / "absent.png")


def test_encoding_a_corrupt_file_is_rejected(tmp_path: Path) -> None:
    target = tmp_path / "broken.png"
    target.write_bytes(b"not an image at all")

    with pytest.raises(UnreadableImageError):
        load_for_encoding(target)


def test_non_positive_max_edge_is_rejected(tmp_path: Path) -> None:
    target = write_image(tmp_path / "cat.png")

    with pytest.raises(ValueError, match="max_edge must be positive"):
        load_for_encoding(target, max_edge=0)


def test_in_memory_frame_can_be_encoded() -> None:
    """Video frames arrive already decoded, so they skip the file path entirely."""
    frame = Image.new("RGB", (1920, 1080), (10, 10, 200))

    payload = encode_for_worker(frame, max_edge=256)

    with Image.open(io.BytesIO(payload)) as decoded:
        assert max(decoded.size) == 256


def test_encoding_a_non_image_is_rejected() -> None:
    with pytest.raises(TypeError, match="expected a PIL image"):
        encode_for_worker(b"raw bytes")


def test_encoded_payload_is_deterministic(tmp_path: Path) -> None:
    target = write_image(tmp_path / "cat.png")

    assert load_for_encoding(target) == load_for_encoding(target)
