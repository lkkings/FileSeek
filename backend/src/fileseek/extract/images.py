"""Reads image dimensions and prepares pixels for encoding.

Images are downscaled before they reach the model worker: the encoder resizes to
its own small input anyway, so sending full-resolution pixels through the process
boundary would cost memory and transfer for nothing.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

# Comfortably above the encoders' input size, so no detail they can use is lost.
DEFAULT_MAX_EDGE = 512


class UnreadableImageError(RuntimeError):
    def __init__(self, path: Path, reason: str) -> None:
        super().__init__(f"could not read image {path.name}: {reason}")
        self.path = path
        self.reason = reason


@dataclass(frozen=True)
class ImageMetadata:
    width: int
    height: int
    image_format: str

    @property
    def pixels(self) -> int:
        return self.width * self.height


def read_metadata(path: Path) -> ImageMetadata:
    """Read dimensions without decoding the whole image."""
    from PIL import Image, UnidentifiedImageError

    if not path.is_file():
        raise UnreadableImageError(path, "file does not exist")
    try:
        with Image.open(path) as image:
            return ImageMetadata(
                width=image.width,
                height=image.height,
                image_format=(image.format or "unknown").lower(),
            )
    except (UnidentifiedImageError, OSError, ValueError) as error:
        raise UnreadableImageError(path, str(error)) from error


def load_for_encoding(path: Path, max_edge: int = DEFAULT_MAX_EDGE) -> bytes:
    """Return the image as downscaled RGB PNG bytes, ready for the worker."""
    from PIL import Image, UnidentifiedImageError

    if not path.is_file():
        raise UnreadableImageError(path, "file does not exist")
    if max_edge < 1:
        raise ValueError(f"max_edge must be positive, got {max_edge}")

    try:
        with Image.open(path) as image:
            image.load()
            return encode_for_worker(image, max_edge)
    except (UnidentifiedImageError, OSError, ValueError) as error:
        raise UnreadableImageError(path, str(error)) from error


def encode_for_worker(image: object, max_edge: int = DEFAULT_MAX_EDGE) -> bytes:
    """Normalise any decoded image (a file, or a video frame) to PNG bytes."""
    from PIL import Image

    if not isinstance(image, Image.Image):
        raise TypeError(f"expected a PIL image, got {type(image).__name__}")

    # RGB regardless of source mode: palette, greyscale and alpha images would
    # otherwise reach the encoder with a channel count it does not expect.
    prepared = image.convert("RGB")
    longest = max(prepared.width, prepared.height)
    if longest > max_edge:
        scale = max_edge / longest
        prepared = prepared.resize(
            (max(1, round(prepared.width * scale)), max(1, round(prepared.height * scale))),
            Image.Resampling.LANCZOS,
        )

    buffer = io.BytesIO()
    prepared.save(buffer, format="PNG")
    return buffer.getvalue()
