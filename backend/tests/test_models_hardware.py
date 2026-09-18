import pytest

from fileseek.models.hardware import HardwareProfile, TorchProbe, detect_hardware


class FakeProbe:
    def __init__(
        self,
        cuda: bool = False,
        mps: bool = False,
        vram: int | None = None,
        name: str | None = None,
        raises: str | None = None,
    ) -> None:
        self._cuda = cuda
        self._mps = mps
        self._vram = vram
        self._name = name
        self._raises = raises

    def _maybe_raise(self, method: str) -> None:
        if self._raises == method:
            raise RuntimeError(f"{method} exploded")

    def cuda_is_available(self) -> bool:
        self._maybe_raise("cuda_is_available")
        return self._cuda

    def mps_is_available(self) -> bool:
        self._maybe_raise("mps_is_available")
        return self._mps

    def cuda_total_memory(self) -> int | None:
        self._maybe_raise("cuda_total_memory")
        return self._vram

    def cuda_device_name(self) -> str | None:
        self._maybe_raise("cuda_device_name")
        return self._name


def test_cuda_machine_is_detected() -> None:
    profile = detect_hardware(
        FakeProbe(cuda=True, vram=12 * 1024**3, name="NVIDIA GeForce RTX 4070")
    )

    assert profile.has_cuda is True
    assert profile.has_gpu is True
    assert profile.vram_bytes == 12 * 1024**3
    assert profile.device_name == "NVIDIA GeForce RTX 4070"


def test_apple_silicon_is_detected() -> None:
    profile = detect_hardware(FakeProbe(mps=True))

    assert profile.has_mps is True
    assert profile.has_gpu is True
    assert profile.has_cuda is False


def test_cpu_only_machine_reports_no_gpu() -> None:
    profile = detect_hardware(FakeProbe())

    assert profile.has_gpu is False
    assert profile.vram_bytes is None


def test_cuda_takes_precedence_over_mps() -> None:
    profile = detect_hardware(FakeProbe(cuda=True, mps=True, vram=8 * 1024**3))

    assert profile.has_cuda is True
    assert profile.has_mps is False


@pytest.mark.parametrize(
    "failing",
    ["cuda_is_available", "mps_is_available", "cuda_total_memory", "cuda_device_name"],
)
def test_probe_failure_degrades_instead_of_raising(failing: str) -> None:
    probe = FakeProbe(cuda=failing not in {"cuda_is_available"}, mps=True, raises=failing)

    profile = detect_hardware(probe)

    assert isinstance(profile, HardwareProfile)


def test_broken_driver_falls_back_to_cpu() -> None:
    profile = detect_hardware(FakeProbe(raises="cuda_is_available"))

    assert profile.has_gpu is False


def test_missing_vram_reading_still_reports_cuda() -> None:
    profile = detect_hardware(FakeProbe(cuda=True, raises="cuda_total_memory"))

    assert profile.has_cuda is True
    assert profile.vram_bytes is None


def test_describe_names_the_cuda_device_and_vram() -> None:
    profile = HardwareProfile(has_cuda=True, vram_bytes=8 * 1024**3, device_name="RTX 3070")

    assert profile.describe() == "RTX 3070 (8.0 GB VRAM)"


def test_describe_handles_cuda_without_details() -> None:
    assert HardwareProfile(has_cuda=True).describe() == "CUDA device"


def test_describe_names_mps_and_cpu() -> None:
    assert HardwareProfile(has_mps=True).describe() == "Apple Silicon (MPS)"
    assert HardwareProfile().describe() == "CPU"


def test_real_torch_probe_answers_without_raising() -> None:
    """The bundled torch is a CPU build, so this must report no CUDA rather than fail."""
    profile = detect_hardware(TorchProbe())

    assert isinstance(profile.has_cuda, bool)
    assert isinstance(profile.has_mps, bool)


def test_real_torch_probe_memory_and_name_match_availability() -> None:
    probe = TorchProbe()

    if probe.cuda_is_available():
        assert probe.cuda_total_memory() is not None
        assert probe.cuda_device_name() is not None
    else:
        assert probe.cuda_total_memory() is None
        assert probe.cuda_device_name() is None


def test_detect_hardware_defaults_to_the_real_probe() -> None:
    assert isinstance(detect_hardware(), HardwareProfile)
