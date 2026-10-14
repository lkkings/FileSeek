from __future__ import annotations

import logging
from pathlib import Path

import av
from io import BytesIO
from PIL import Image

from fileseek.features.tasks.domain.ports.video_sampler import (
    VideoFrame,
    VideoKeyframe,
    VideoSamplerPort,
)
from fileseek.features.tasks.domain.exceptions import VideoProcessError
from fileseek.features.tasks.infrastructure.file_processor.perceptual_hash import phash

logger = logging.getLogger(__name__)

def image_to_bytes(image: Image.Image, format: str = "PNG") -> bytes:
    buffer = BytesIO()
    image.save(buffer, format=format)
    return buffer.getvalue()


class VideoSampler(VideoSamplerPort):
    """视频采样与关键帧提取服务。"""

    def __init__(
        self,
        sample_every_n_frames: int = 30,
        hash_threshold: int = 10,
    ) -> None:
        self.sample_every_n_frames = sample_every_n_frames
        self.hash_threshold = hash_threshold

    def extract_keyframes(
        self,
        video_path: Path,
    ) -> tuple[VideoKeyframe, ...]:
        try:
            container = av.open(str(video_path))
        except (av.FFmpegError, OSError) as exc:
            raise VideoProcessError(
                f"无法打开视频文件: {video_path}"
            ) from exc

        try:
            stream = container.streams.video[0]
        except IndexError as exc:
            container.close()
            raise VideoProcessError(
                f"视频文件不包含视频流: {video_path}"
            ) from exc

        sampled: list[tuple[float, Image.Image]] = []
        total_duration = 0.0

        try:
            if stream.duration:
                total_duration = float(
                    stream.duration * stream.time_base
                )

            for frame_index, frame in enumerate(container.decode(stream)):
                if frame_index % self.sample_every_n_frames != 0:
                    continue

                if frame.pts is None:
                    continue

                timestamp = float(
                    frame.pts * stream.time_base
                )

                sampled.append(
                    (
                        timestamp,
                        frame.to_image(),
                    )
                )

        except av.FFmpegError as exc:
            raise VideoProcessError(
                f"视频解码失败: {video_path}"
            ) from exc
        finally:
            container.close()

        if not sampled:
            return ()

        selected: list[tuple[float, Image.Image]] = []
        previous_hash = None

        for timestamp, image in sampled:
            current_hash = phash(image)

            if (
                previous_hash is None
                or (current_hash - previous_hash) > self.hash_threshold
            ):
                selected.append((timestamp, image))
                previous_hash = current_hash

        if not selected:
            return ()

        if not total_duration:
            total_duration = selected[-1][0]

        keyframes: list[VideoKeyframe] = []

        for index, (start_time, image) in enumerate(selected):
            end_time = (
                selected[index + 1][0]
                if index + 1 < len(selected)
                else total_duration
            )

            keyframes.append(
                VideoKeyframe(
                    start_time=start_time,
                    end_time=end_time,
                    frame=VideoFrame(data=image_to_bytes(image)),
                )
            )

        return tuple(keyframes)