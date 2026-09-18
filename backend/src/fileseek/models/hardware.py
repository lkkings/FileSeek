"""Detects what compute the machine actually has.

Probing is behind a Protocol so tier selection can be tested without owning one
GPU of each kind.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class HardwareProbe(Protocol):
    """The parts of torch this module needs, narrowed to what it asks."""

    def cuda_is_available(self) -> bool: ...

    def mps_is_available(self) -> bool: ...

    def cuda_total_memory(self) -> int | None: ...

    def cuda_device_name(self) -> str | None: ...


@dataclass(frozen=True)
class HardwareProfile:
    has_cuda: bool = False
    has_mps: bool = False
    vram_bytes: int | None = None
    device_name: str | None = None

    @property
    def has_gpu(self) -> bool:
        return self.has_cuda or self.has_mps

    def describe(self) -> str:
        if self.has_cuda:
            name = self.device_name or "CUDA device"
            if self.vram_bytes is not None:
                return f"{name} ({self.vram_bytes / 1024**3:.1f} GB VRAM)"
            return name
        if self.has_mps:
            return "Apple Silicon (MPS)"
        return "CPU"


class TorchProbe:
    """Reads the real torch runtime, tolerating a torch built without CUDA."""

    def cuda_is_available(self) -> bool:
        import torch

        return bool(torch.cuda.is_available())

    def mps_is_available(self) -> bool:
        import torch

        backend = getattr(torch.backends, "mps", None)
        if backend is None:
            return False
        return bool(backend.is_available())

    def cuda_total_memory(self) -> int | None:
        import torch

        if not torch.cuda.is_available():
            return None
        return int(torch.cuda.get_device_properties(0).total_memory)

    def cuda_device_name(self) -> str | None:
        import torch

        if not torch.cuda.is_available():
            return None
        return str(torch.cuda.get_device_name(0))


def detect_hardware(probe: HardwareProbe | None = None) -> HardwareProfile:
    """Build a profile of the available accelerators.

    A probe that raises is treated as "no accelerator": a broken driver should
    degrade to CPU rather than stop the app from starting.
    """
    active = probe if probe is not None else TorchProbe()

    try:
        has_cuda = active.cuda_is_available()
    except Exception:
        has_cuda = False

    if has_cuda:
        try:
            vram = active.cuda_total_memory()
        except Exception:
            vram = None
        try:
            name = active.cuda_device_name()
        except Exception:
            name = None
        return HardwareProfile(has_cuda=True, vram_bytes=vram, device_name=name)

    try:
        has_mps = active.mps_is_available()
    except Exception:
        has_mps = False

    return HardwareProfile(has_mps=has_mps)
