"""jina-clip-v2 推理时的图片预处理。

模型仓库的 `JinaCLIPImageProcessor` 是远程代码，推理分支只做这几步：
最短边缩放、中心裁剪、/255、按 mean/std 归一化、转 CHW。为了这几步要装 torch 和
torchvision，于是在这里用 Pillow + numpy 重写，配置仍从 `preprocessor_config.json` 读。

取整规则照抄 torchvision，这样和旧实现的差异只剩插值实现本身：torchvision 对 PIL 输入
调用的就是 `Image.resize`，所以实测几乎逐像素一致。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from fileseek.shared.domain.exceptions import ModelLoadError

if TYPE_CHECKING:
    from PIL import Image

PREPROCESSOR_CONFIG = "preprocessor_config.json"

# OpenAI CLIP 的默认值，和远程代码一致；配置里缺字段时用。
_DEFAULT_MEAN = (0.48145466, 0.4578275, 0.40821073)
_DEFAULT_STD = (0.26862954, 0.26130258, 0.27577711)


class ClipImagePreprocessor:
    """把一批 PIL 图片变成 `(N, 3, size, size)` 的 float32 数组。"""

    def __init__(
        self,
        *,
        size: int,
        mean: tuple[float, float, float] = _DEFAULT_MEAN,
        std: tuple[float, float, float] = _DEFAULT_STD,
        interpolation: str = "bicubic",
    ) -> None:
        from PIL import Image

        resample = {
            "bicubic": Image.Resampling.BICUBIC,
            "bilinear": Image.Resampling.BILINEAR,
        }.get(interpolation)
        if resample is None:
            raise ModelLoadError(f"不支持的图片插值方式: {interpolation}")
        self.size = size
        self._resample = resample
        self._mean = np.asarray(mean, dtype=np.float32).reshape(3, 1, 1)
        self._std = np.asarray(std, dtype=np.float32).reshape(3, 1, 1)

    @classmethod
    def from_dir(cls, model_dir: Path) -> ClipImagePreprocessor:
        """从模型目录里的 `preprocessor_config.json` 构造。"""
        path = model_dir / PREPROCESSOR_CONFIG
        try:
            config = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ModelLoadError(f"无法读取图片预处理配置: {path}") from exc

        resize_mode = config.get("resize_mode", "shortest")
        if resize_mode != "shortest":
            raise ModelLoadError(f"不支持的图片缩放方式: {resize_mode}")
        size = config.get("size", 224)
        if isinstance(size, list | tuple):
            if len(size) != 2 or size[0] != size[1]:
                raise ModelLoadError(f"只支持正方形的预处理尺寸: {size}")
            size = size[0]

        return cls(
            size=int(size),
            mean=_channels(config.get("mean", _DEFAULT_MEAN)),
            std=_channels(config.get("std", _DEFAULT_STD)),
            interpolation=config.get("interpolation", "bicubic"),
        )

    def __call__(self, images: list[Image.Image]) -> np.ndarray:
        return np.stack([self._transform(image) for image in images])

    def _transform(self, image: Image.Image) -> np.ndarray:
        image = image.convert("RGB")
        width, height = image.size
        size = self.size

        # torchvision `Resize(int)`：短边到 size，长边 int(size * long / short)。
        if width <= height:
            new_size = (size, int(size * height / width))
        else:
            new_size = (int(size * width / height), size)
        if new_size != image.size:
            image = image.resize(new_size, self._resample)

        # torchvision `CenterCrop`：round 而不是地板除，奇数差时偏向右下。
        width, height = image.size
        top = int(round((height - size) / 2.0))
        left = int(round((width - size) / 2.0))
        image = image.crop((left, top, left + size, top + size))

        pixels = np.asarray(image, dtype=np.float32).transpose(2, 0, 1) / 255.0
        return (pixels - self._mean) / self._std


def _channels(value: object) -> tuple[float, float, float]:
    if isinstance(value, int | float):
        return (float(value),) * 3
    if isinstance(value, list | tuple) and len(value) == 3:
        return (float(value[0]), float(value[1]), float(value[2]))
    raise ModelLoadError(f"图片归一化参数必须是 1 个或 3 个数: {value}")
