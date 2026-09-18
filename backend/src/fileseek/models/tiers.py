"""Which models to load, and on what device.

Two tiers: a high-accuracy one for machines with a real GPU, and a light one that
stays usable on CPU. Both use Chinese-aligned weights, because the product's
queries are written in Chinese (see design decision 7).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from fileseek.models.hardware import HardwareProfile, detect_hardware

ModelTier = Literal["gpu", "cpu"]

DevicePreference = Literal["auto", "gpu", "cpu"]

Device = Literal["cuda", "mps", "cpu"]

# ViT-L/14 plus the large text encoder need headroom for batched frames; below
# this the GPU tier would spend its time thrashing, so CPU-tier weights win.
MIN_GPU_VRAM_BYTES = 6 * 1024**3


@dataclass(frozen=True)
class ModelSpec:
    repo_id: str
    dimensions: int
    # Some models ship inside their pip package (RapidOCR carries its own ONNX
    # files), so there is nothing to download and nothing to verify on disk.
    bundled: bool = False


@dataclass(frozen=True)
class ModelBundle:
    """The three models one tier needs, and the vector widths they produce."""

    tier: ModelTier
    image: ModelSpec
    text: ModelSpec
    ocr: ModelSpec

    @property
    def image_dimensions(self) -> int:
        return self.image.dimensions

    @property
    def text_dimensions(self) -> int:
        return self.text.dimensions


# Chinese-CLIP is loaded through transformers, so these are plain HF repo ids.
GPU_BUNDLE = ModelBundle(
    tier="gpu",
    image=ModelSpec("OFA-Sys/chinese-clip-vit-large-patch14", dimensions=768),
    text=ModelSpec("intfloat/multilingual-e5-large", dimensions=1024),
    ocr=ModelSpec("rapidocr-onnxruntime", dimensions=0, bundled=True),
)

CPU_BUNDLE = ModelBundle(
    tier="cpu",
    image=ModelSpec("OFA-Sys/chinese-clip-vit-base-patch16", dimensions=512),
    text=ModelSpec("intfloat/multilingual-e5-small", dimensions=384),
    ocr=ModelSpec("rapidocr-onnxruntime", dimensions=0, bundled=True),
)

BUNDLES: dict[ModelTier, ModelBundle] = {"gpu": GPU_BUNDLE, "cpu": CPU_BUNDLE}


@dataclass(frozen=True)
class ModelSelection:
    """The chosen tier and device, with a reason the settings screen can show."""

    tier: ModelTier
    device: Device
    reason: str
    profile: HardwareProfile

    @property
    def bundle(self) -> ModelBundle:
        return BUNDLES[self.tier]

    def describe(self) -> str:
        return f"{self.tier} tier on {self.device}: {self.reason}"


def select_models(
    preference: DevicePreference = "auto",
    profile: HardwareProfile | None = None,
    min_vram_bytes: int = MIN_GPU_VRAM_BYTES,
) -> ModelSelection:
    """Pick a tier, honouring an explicit user preference over detection."""
    resolved = profile if profile is not None else detect_hardware()

    if preference == "cpu":
        return ModelSelection(
            tier="cpu", device="cpu", reason="CPU requested by user", profile=resolved
        )

    if preference == "gpu":
        if resolved.has_cuda:
            return ModelSelection(
                tier="gpu", device="cuda", reason="GPU requested by user", profile=resolved
            )
        if resolved.has_mps:
            return ModelSelection(
                tier="gpu", device="mps", reason="GPU requested by user", profile=resolved
            )
        return ModelSelection(
            tier="cpu",
            device="cpu",
            reason="GPU requested by user but none detected, using CPU",
            profile=resolved,
        )

    if resolved.has_cuda:
        if resolved.vram_bytes is not None and resolved.vram_bytes < min_vram_bytes:
            return ModelSelection(
                tier="cpu",
                device="cuda",
                reason=(
                    f"GPU has {resolved.vram_bytes / 1024**3:.1f} GB VRAM, "
                    "below the threshold for the large models"
                ),
                profile=resolved,
            )
        return ModelSelection(
            tier="gpu", device="cuda", reason=f"detected {resolved.describe()}", profile=resolved
        )

    if resolved.has_mps:
        return ModelSelection(
            tier="gpu", device="mps", reason="detected Apple Silicon (MPS)", profile=resolved
        )

    return ModelSelection(
        tier="cpu", device="cpu", reason="no GPU detected, using CPU models", profile=resolved
    )


def downgrade_to_cpu(selection: ModelSelection, cause: str) -> ModelSelection:
    """Fall back to CPU after an out-of-memory load, rather than failing outright."""
    return ModelSelection(
        tier="cpu",
        device="cpu",
        reason=f"downgraded from {selection.tier} tier on {selection.device}: {cause}",
        profile=selection.profile,
    )
