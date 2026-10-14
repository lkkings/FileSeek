"""视频关键帧去重用的感知哈希（DCT phash）。

算法与 `imagehash.phash` 相同：灰度、LANCZOS 缩到 32x32、二维 DCT-II、取左上 8x8、
和中位数比较得到 64 位。imagehash 为一次 DCT 要带上 scipy 和 PyWavelets，这里用一个
32x32 的余弦基矩阵做两次矩阵乘法代替。系数整体缩放不影响和中位数的比较，所以不用
关心归一化方式。
"""

from __future__ import annotations

from functools import cache
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from PIL import Image

_HASH_SIZE = 8
_HIGHFREQ_FACTOR = 4
_ZERO_EPSILON = 1e-9


class PerceptualHash:
    """64 位布尔哈希；`a - b` 是汉明距离，和 `imagehash.ImageHash` 用法一致。"""

    __slots__ = ("bits",)

    def __init__(self, bits: np.ndarray) -> None:
        self.bits = bits

    def __sub__(self, other: PerceptualHash) -> int:
        if self.bits.shape != other.bits.shape:
            raise TypeError("哈希长度不一致")
        return int(np.count_nonzero(self.bits != other.bits))


@cache
def _dct_matrix(n: int) -> np.ndarray:
    """未归一化的 DCT-II 基：`C[k, i] = 2 cos(pi (2i + 1) k / 2n)`，与 scipy 默认一致。"""
    k = np.arange(n).reshape(-1, 1)
    i = np.arange(n).reshape(1, -1)
    return 2.0 * np.cos(np.pi * (2 * i + 1) * k / (2 * n))


def phash(image: Image.Image) -> PerceptualHash:
    from PIL import Image

    img_size = _HASH_SIZE * _HIGHFREQ_FACTOR
    small = image.convert("L").resize((img_size, img_size), Image.Resampling.LANCZOS)
    pixels = np.asarray(small, dtype=np.float64)
    basis = _dct_matrix(img_size)
    dct = basis @ pixels @ basis.T
    low = dct[:_HASH_SIZE, :_HASH_SIZE]
    # 纯色、单向渐变这类帧，大部分系数在数学上是 0，scipy 的 FFT 也恰好给出 0；
    # 矩阵乘法却留下 ±1e-11 的噪声。中位数正好是 0 时，噪声的正负号会随机翻转
    # 一半的位。把相对最大系数可以忽略的值归零，结果才和 scipy 一致。
    low = np.where(np.abs(low) < _ZERO_EPSILON * max(float(np.abs(low).max()), 1.0), 0.0, low)
    return PerceptualHash((low > np.median(low)).flatten())
