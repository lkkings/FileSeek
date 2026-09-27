from __future__ import annotations

from functools import lru_cache

from fileseek.config.settings import get_settings
from fileseek.infrastructure.ocr.base import OCRPort
from fileseek.infrastructure.ocr.rapidocr import RapidOCROCR


@lru_cache
def get_ocr_service() -> OCRPort:
    """进程内共享的向量存储。"""
    settings = get_settings()
    return OCRFactory.create(
        provider=settings.ocr_provider
    )


class OCRFactory:
    """OCR 实现工厂。"""

    _DEFAULT_PROVIDER = "rapidocr"

    @classmethod
    def create(
        cls,
        provider: str = _DEFAULT_PROVIDER,
    ) -> OCRPort:
        """创建 OCR 实现。

        Args:
            provider: OCR 实现类型。

        Returns:
            OCRPort: OCR 能力抽象。

        Raises:
            ValueError: 不支持的 OCR provider。
        """
        normalized_provider = provider.strip().lower()

        if normalized_provider == "rapidocr":
            return RapidOCROCR()

        raise ValueError(
            f"不支持的 OCR provider: {provider}"
        )
