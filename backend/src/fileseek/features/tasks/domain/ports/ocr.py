from __future__ import annotations

from pathlib import Path
from typing import Protocol

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ImageContent:
    """图片内容。"""

    image: object | str = None
    ocr_text: str | None = None

class OCRPort(Protocol):
    def extract_text(self, path: Path) -> str: ...


