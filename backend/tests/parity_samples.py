"""对照基准用的样本：`scripts/make_parity_fixtures.py` 和对照测试共用同一份生成逻辑。

图片、文本、视频帧全部按固定种子现场生成，仓库里只存旧实现算出的结果。
"""

from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw

# name -> (width, height, mode, 预处理目标边长)。目标边长取小值让基准文件保持在几百 KB，
# 512 只留一条，确认真实尺寸下的行为也一致。
PREPROCESS_CASES: dict[str, tuple[int, int, str, int]] = {
    "landscape": (300, 200, "RGB", 64),
    "portrait": (157, 333, "RGB", 64),
    "odd_edges": (101, 77, "RGB", 63),
    "extreme_wide": (1200, 41, "RGB", 64),
    "extreme_tall": (37, 900, "RGB", 64),
    "upscale": (20, 30, "RGB", 64),
    "exact": (64, 64, "RGB", 64),
    "grayscale": (180, 120, "L", 64),
    "rgba": (140, 190, "RGBA", 64),
    "palette": (160, 100, "P", 64),
    "full_size": (640, 480, "RGB", 512),
}

# 图片向量基准：真实 512 预处理 + 模型推理。
EMBEDDING_IMAGE_SIZES: list[tuple[int, int, str]] = [
    (640, 480, "RGB"),
    (333, 777, "RGB"),
    (256, 256, "RGBA"),
]


def sample_image(width: int, height: int, mode: str, seed: int = 0) -> Image.Image:
    """渐变底加几何图形和噪声：既有平滑区域也有锐利边缘，插值差异能暴露出来。"""
    rng = np.random.default_rng(seed + width * 7 + height)
    y, x = np.mgrid[0:height, 0:width]
    base = np.stack(
        [
            x * 255 / max(width - 1, 1),
            y * 255 / max(height - 1, 1),
            (x + y) * 127 / max(width + height - 2, 1),
        ],
        axis=-1,
    )
    noise = rng.normal(0, 12, size=base.shape)
    image = Image.fromarray(np.clip(base + noise, 0, 255).astype(np.uint8), "RGB")
    draw = ImageDraw.Draw(image)
    draw.ellipse((width * 0.2, height * 0.2, width * 0.6, height * 0.7), fill=(240, 30, 60))
    draw.rectangle((width * 0.55, height * 0.1, width * 0.9, height * 0.45), fill=(20, 200, 90))
    if mode == "RGB":
        return image
    if mode == "L":
        return image.convert("L")
    if mode == "RGBA":
        alpha = Image.fromarray((x * 255 / max(width - 1, 1)).astype(np.uint8), "L")
        rgba = image.convert("RGBA")
        rgba.putalpha(alpha)
        return rgba
    if mode == "P":
        return image.convert("P", palette=Image.Palette.ADAPTIVE, colors=32)
    raise ValueError(mode)


def sample_texts() -> list[str]:
    """覆盖中英文、空白、特殊字符，以及超过 77 和超过 8194 token 的文本。"""
    rng = np.random.default_rng(1)
    words = ["file", "search", "向量", "检索", "文档", "semantic", "🙂", "naïve", "数据库"]
    long_text = " ".join(rng.choice(words, size=400))
    very_long = " ".join(rng.choice(words, size=12000))
    return [
        "hello world",
        "本地优先的语义文件搜索",
        "Represent the query for retrieving evidence documents: 去年的发票",
        "  leading and trailing spaces  ",
        "",
        "Mixed 中英文 text with numbers 12345 and symbols !@#$%^&*()",
        "tabs\tand\nnewlines\r\nhere",
        "<s> </s> <pad> <mask> literal special tokens",
        "ÀÉÎÕÜ ß ﬁ ① ＡＢＣ full-width and ligatures",
        long_text,
        very_long,
    ]


def phash_frames() -> dict[str, Image.Image]:
    """纯色、渐变、噪声、平移、轻微压缩：视频去重会遇到的几类相邻帧。"""
    rng = np.random.default_rng(2)
    base = sample_image(320, 240, "RGB", seed=3)
    shifted = Image.new("RGB", base.size)
    shifted.paste(base, (6, 4))
    noisy = np.asarray(base).astype(np.int16) + rng.integers(-8, 9, size=(240, 320, 3))
    gradient = np.tile(np.linspace(0, 255, 320, dtype=np.uint8), (240, 1))
    return {
        "solid": Image.new("RGB", (320, 240), (120, 80, 200)),
        "gradient": Image.fromarray(gradient, "L").convert("RGB"),
        "base": base,
        "shifted": shifted,
        "noisy": Image.fromarray(np.clip(noisy, 0, 255).astype(np.uint8), "RGB"),
        "other": sample_image(320, 240, "RGB", seed=99).transpose(Image.Transpose.ROTATE_180),
        "small": sample_image(64, 48, "RGB", seed=5),
    }
