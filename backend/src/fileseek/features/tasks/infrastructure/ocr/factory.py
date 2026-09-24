from __future__ import annotations

from fileseek.features.tasks.domain.ports import OCRPort
from fileseek.features.tasks.infrastructure.ocr.rapidocr import RapidOCROCR


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