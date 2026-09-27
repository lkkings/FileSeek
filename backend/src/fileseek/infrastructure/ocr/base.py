from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ImageContent:
    """图片内容。"""

    image: object | str = None
    ocr_text: str | None = None

class OCRPort(Protocol):
    def extract_text(self, path: Path) -> str: ...


