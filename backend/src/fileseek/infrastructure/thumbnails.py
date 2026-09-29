from __future__ import annotations

from collections.abc import Callable
from io import BytesIO
from pathlib import Path
from typing import Literal, cast

import av
import pypdfium2 as pdfium
from PIL import Image, ImageOps

PreviewSize = Literal["list", "detail"]

PREVIEW_DIMENSIONS: dict[PreviewSize, tuple[int, int]] = {
    "list": (96, 96),
    "detail": (640, 640),
}


class ThumbnailGenerationError(RuntimeError):
    """Raised when an image or video thumbnail cannot be generated."""


class ThumbnailGenerator:
    """Generates bounded WebP thumbnails for images and videos."""

    def generate_image_thumbnail(self, source: bytes, size: PreviewSize = "list") -> bytes:
        try:
            with Image.open(BytesIO(source)) as image:
                oriented = ImageOps.exif_transpose(image)
                return self._encode_webp(oriented, size)
        except (OSError, ValueError) as exc:
            raise ThumbnailGenerationError("Unable to decode the image file") from exc

    def generate_video_thumbnail(self, source: Path | str, size: PreviewSize = "list") -> bytes:
        try:
            container = av.open(str(source))
        except (av.FFmpegError, OSError) as exc:
            raise ThumbnailGenerationError("Unable to open the video file") from exc

        try:
            video_stream = container.streams.video[0]
            for frame in container.decode(video_stream):
                frame_to_image = cast(Callable[[], Image.Image], frame.to_image)
                return self._encode_webp(frame_to_image(), size)
        except (IndexError, av.FFmpegError, OSError, ValueError) as exc:
            raise ThumbnailGenerationError("Unable to decode a video frame") from exc
        finally:
            container.close()

        raise ThumbnailGenerationError("The video does not contain a decodable frame")

    def generate_pdf_thumbnail(self, source: bytes, size: PreviewSize = "list") -> bytes:
        try:
            document = pdfium.PdfDocument(source, autoclose=True)
        except (pdfium.PdfiumError, OSError, ValueError) as exc:
            raise ThumbnailGenerationError("Unable to open the PDF file") from exc

        try:
            page = document[0]
            page_width, page_height = page.get_size()
            target_width, target_height = PREVIEW_DIMENSIONS[size]
            scale = min(
                target_width / max(page_width, 1),
                target_height / max(page_height, 1),
            )
            bitmap = page.render(scale=scale)
            try:
                return self._encode_webp(bitmap.to_pil(), size)
            finally:
                bitmap.close()
        except (IndexError, pdfium.PdfiumError, OSError, ValueError) as exc:
            raise ThumbnailGenerationError("Unable to render the first PDF page") from exc
        finally:
            document.close()

    def _encode_webp(self, image: Image.Image, size: PreviewSize) -> bytes:
        try:
            image.thumbnail(
                PREVIEW_DIMENSIONS[size],
                resample=Image.Resampling.LANCZOS,
                reducing_gap=3.0,
            )
            buffer = BytesIO()
            image.save(
                buffer,
                format="WEBP",
                quality=85,
                method=6,
            )
            return buffer.getvalue()
        except (OSError, ValueError) as exc:
            raise ThumbnailGenerationError("Unable to encode the WebP thumbnail") from exc
