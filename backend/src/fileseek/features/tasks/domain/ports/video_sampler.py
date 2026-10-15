from __future__ import annotations

from pathlib import Path
from typing import Protocol

from dataclasses import dataclass


@dataclass(frozen=True)
class VideoFrame:
    """视频帧数据。"""

    data: bytes


@dataclass(frozen=True)
class VideoKeyframe:
    """视频关键帧。"""

    start_time: float
    end_time: float
    frame: VideoFrame


class VideoSamplerPort(Protocol):
    def extract_keyframes(self, path: Path) -> tuple[VideoKeyframe, ...]: ...
