"""OCR 文字识别服务。

使用 rapidocr-onnxruntime 进行图片文字提取，支持中英文混排。
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import TYPE_CHECKING

from fileseek.features.tasks.domain.ports import OCRPort
from fileseek.features.tasks.domain.exceptions import ImageProcessError

if TYPE_CHECKING:
    from rapidocr_onnxruntime import RapidOCR

logger = logging.getLogger(__name__)



class OCRService(OCRPort):
    """OCR 文字识别服务。

    模型懒加载：首次调用 extract_text 时才初始化 RapidOCR（避免拖慢应用启动），
    加载后复用同一实例。
    """

    def __init__(self) -> None:
        self._ocr: RapidOCR | None = None
        self._lock = threading.Lock()

    def _ensure_loaded(self) -> RapidOCR:
        if self._ocr is not None:
            return self._ocr

        with self._lock:
            if self._ocr is None:
                from rapidocr_onnxruntime import RapidOCR

                self._ocr = RapidOCR()
            return self._ocr

    def extract_text(self, image_path: Path) -> str:
        """从图片中提取文字。

        Args:
            image_path: 图片文件路径

        Returns:
            识别到的文本内容，无文字或识别失败时返回空字符串

        Raises:
            ImageProcessError: 图片文件不存在或无法打开
        """
        if not image_path.exists():
            msg = f"图片文件不存在: {image_path}"
            raise ImageProcessError(msg)

        ocr = self._ensure_loaded()

        try:
            result, _elapse = ocr(str(image_path))
        except Exception:
            # 很多图片本身无文字或格式边界情况会导致识别异常，
            # 按设计返回空字符串而非向上抛出。
            logger.warning("OCR 识别异常，返回空文本: %s", image_path, exc_info=True)
            return ""

        if not result:
            return ""

        return "\n".join(entry[1] for entry in result)
