"""Encoder doubles for the worker tests.

These live in their own module because the worker spawns a child process that
imports the factory by dotted path; a fixture defined inside a test function
would not be importable there.
"""

from __future__ import annotations

import time
from collections.abc import Sequence

from fileseek.models.tiers import ModelSelection
from fileseek.models.worker import Encoders, OutOfMemoryError

IMAGE_DIMENSIONS = 4
TEXT_DIMENSIONS = 3


class EchoEncoders:
    """Deterministic vectors derived from the input, so assertions stay exact."""

    def __init__(self, selection: ModelSelection) -> None:
        self.selection = selection

    def encode_images(self, images: Sequence[bytes]) -> list[list[float]]:
        return [[float(len(image)), 1.0, 0.0, 0.0] for image in images]

    def encode_texts(self, texts: Sequence[str]) -> list[list[float]]:
        return [[float(len(text)), 0.0, 1.0] for text in texts]

    def encode_query(self, query: str) -> list[float]:
        return [float(len(query)), 0.0, 0.0, 1.0]

    def encode_text_query(self, query: str) -> list[float]:
        return [float(len(query)), 1.0, 0.0]

    def recognize_text(self, image: bytes) -> str:
        return f"ocr:{len(image)}"

    def describe(self) -> tuple[str, str, int, int]:
        return (
            self.selection.bundle.image.repo_id,
            self.selection.bundle.text.repo_id,
            IMAGE_DIMENSIONS,
            TEXT_DIMENSIONS,
        )


class ExplodingEncoders(EchoEncoders):
    def encode_images(self, images: Sequence[bytes]) -> list[list[float]]:
        raise RuntimeError("could not decode frame")


class OomEncoders(EchoEncoders):
    def encode_images(self, images: Sequence[bytes]) -> list[list[float]]:
        raise RuntimeError("CUDA out of memory while encoding batch")


def make_echo(selection: ModelSelection) -> Encoders:
    return EchoEncoders(selection)


def make_exploding(selection: ModelSelection) -> Encoders:
    return ExplodingEncoders(selection)


def make_oom_on_encode(selection: ModelSelection) -> Encoders:
    return OomEncoders(selection)


def make_oom_on_gpu_load(selection: ModelSelection) -> Encoders:
    """Fails to load the GPU tier, so the worker must downgrade to CPU."""
    if selection.tier == "gpu":
        raise OutOfMemoryError("CUDA out of memory: tried to allocate 2.5 GiB")
    return EchoEncoders(selection)


def make_broken_load(selection: ModelSelection) -> Encoders:
    raise RuntimeError("model weights are corrupt")


def make_slow_load(selection: ModelSelection) -> Encoders:
    time.sleep(30)
    return EchoEncoders(selection)


not_callable = "this is not a factory"
