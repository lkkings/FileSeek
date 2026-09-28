from io import BytesIO
from pathlib import Path

import av
import pytest
from PIL import Image

from fileseek.infrastructure.thumbnails import (
    PREVIEW_DIMENSIONS,
    ThumbnailGenerationError,
    ThumbnailGenerator,
)


def create_image(width: int, height: int) -> bytes:
    image = Image.new("RGB", (width, height), "#3366aa")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_image_thumbnail_is_resized_and_encoded_as_webp():
    generator = ThumbnailGenerator()

    thumbnail = generator.generate_image_thumbnail(create_image(1600, 900), "list")

    with Image.open(BytesIO(thumbnail)) as image:
        assert image.format == "WEBP"
        assert image.size <= PREVIEW_DIMENSIONS["list"]
        assert image.size == (96, 54)


def test_detail_image_thumbnail_uses_the_larger_bound():
    generator = ThumbnailGenerator()

    thumbnail = generator.generate_image_thumbnail(create_image(1600, 900), "detail")

    with Image.open(BytesIO(thumbnail)) as image:
        assert image.size == (640, 360)


def test_video_thumbnail_uses_the_first_decodable_frame(tmp_path: Path):
    video_path = tmp_path / "sample.mp4"
    write_video(video_path, 320, 240)
    generator = ThumbnailGenerator()

    thumbnail = generator.generate_video_thumbnail(video_path, "list")

    with Image.open(BytesIO(thumbnail)) as image:
        assert image.format == "WEBP"
        assert image.size == (96, 72)


def test_invalid_image_raises_a_thumbnail_generation_error():
    generator = ThumbnailGenerator()

    with pytest.raises(ThumbnailGenerationError, match="image"):
        generator.generate_image_thumbnail(b"not an image")


def test_missing_video_raises_a_thumbnail_generation_error(tmp_path: Path):
    generator = ThumbnailGenerator()

    with pytest.raises(ThumbnailGenerationError, match="video"):
        generator.generate_video_thumbnail(tmp_path / "missing.mp4")


def write_video(path: Path, width: int, height: int) -> None:
    container = av.open(str(path), mode="w")
    stream = container.add_stream("mpeg4", rate=1)
    stream.width = width
    stream.height = height
    stream.pix_fmt = "yuv420p"
    frame = av.VideoFrame.from_image(Image.new("RGB", (width, height), "#aa3366"))

    for packet in stream.encode(frame):
        container.mux(packet)
    for packet in stream.encode():
        container.mux(packet)
    container.close()
