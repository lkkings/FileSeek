"""RapidOCR OCR 实现。

使用 rapidocr-onnxruntime 进行图片文字提取。
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import TYPE_CHECKING

from fileseek.features.tasks.domain.exceptions import ImageProcessError
from fileseek.features.tasks.domain.ports import OCRPort

if TYPE_CHECKING:
    from rapidocr_onnxruntime import RapidOCR

logger = logging.getLogger(__name__)


class RapidOCROCR(OCRPort):
    """RapidOCR OCR 适配器。

    模型采用懒加载，首次调用时才初始化。
    """

    def __init__(self) -> None:
        self._ocr: RapidOCR | None = None
        self._lock = threading.Lock()

    def _ensure_loaded(self) -> RapidOCR:
        """确保 OCR 模型已经加载。"""
        if self._ocr is not None:
            return self._ocr

        with self._lock:
            if self._ocr is None:
                from rapidocr_onnxruntime import RapidOCR

                self._ocr = RapidOCR()

            return self._ocr

    def extract_text(self, image_path: Path) -> str:
        """识别图片中的文字。

        OCR 识别异常按照无文本处理，不向上层传播模型异常。
        """
        if not image_path.is_file():
            raise ImageProcessError(
                f"图片文件不存在: {image_path}"
            )

        ocr = self._ensure_loaded()

        try:
            result, _ = ocr(str(image_path))
        except Exception:
            logger.warning(
                "OCR 识别异常，返回空文本: %s",
                image_path,
                exc_info=True,
            )
            return ""

        if not result:
            return ""

        return "\n".join(
            str(item[1])
            for item in result
            if len(item) > 1 and item[1]
        )