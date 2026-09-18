import pytest

from fileseek.models.hardware import HardwareProfile
from fileseek.models.tiers import (
    BUNDLES,
    CPU_BUNDLE,
    GPU_BUNDLE,
    MIN_GPU_VRAM_BYTES,
    DevicePreference,
    ModelSelection,
    downgrade_to_cpu,
    select_models,
)

BIG_GPU = HardwareProfile(has_cuda=True, vram_bytes=12 * 1024**3, device_name="RTX 4070")
SMALL_GPU = HardwareProfile(has_cuda=True, vram_bytes=2 * 1024**3, device_name="GTX 1050")
APPLE = HardwareProfile(has_mps=True)
CPU_ONLY = HardwareProfile()


def test_capable_gpu_selects_the_gpu_tier() -> None:
    selection = select_models(profile=BIG_GPU)

    assert selection.tier == "gpu"
    assert selection.device == "cuda"
    assert selection.bundle is GPU_BUNDLE
    assert "RTX 4070" in selection.reason


def test_cpu_only_machine_selects_the_light_tier() -> None:
    selection = select_models(profile=CPU_ONLY)

    assert selection.tier == "cpu"
    assert selection.device == "cpu"
    assert selection.bundle is CPU_BUNDLE
    assert "no GPU detected" in selection.reason


def test_apple_silicon_selects_the_gpu_tier_on_mps() -> None:
    selection = select_models(profile=APPLE)

    assert selection.tier == "gpu"
    assert selection.device == "mps"


def test_low_vram_gpu_falls_back_to_light_models() -> None:
    selection = select_models(profile=SMALL_GPU)

    assert selection.tier == "cpu"
    assert selection.device == "cuda"
    assert "below the threshold" in selection.reason


def test_gpu_without_reported_vram_is_trusted() -> None:
    selection = select_models(profile=HardwareProfile(has_cuda=True))

    assert selection.tier == "gpu"


def test_vram_exactly_at_threshold_keeps_the_gpu_tier() -> None:
    profile = HardwareProfile(has_cuda=True, vram_bytes=MIN_GPU_VRAM_BYTES)

    assert select_models(profile=profile).tier == "gpu"


def test_forced_cpu_overrides_a_capable_gpu() -> None:
    selection = select_models(preference="cpu", profile=BIG_GPU)

    assert selection.tier == "cpu"
    assert selection.device == "cpu"
    assert "requested by user" in selection.reason


def test_forced_gpu_uses_cuda_when_present() -> None:
    selection = select_models(preference="gpu", profile=SMALL_GPU)

    assert selection.tier == "gpu"
    assert selection.device == "cuda"
    assert "requested by user" in selection.reason


def test_forced_gpu_uses_mps_on_apple_silicon() -> None:
    selection = select_models(preference="gpu", profile=APPLE)

    assert selection.device == "mps"


def test_forced_gpu_without_hardware_reports_the_fallback() -> None:
    selection = select_models(preference="gpu", profile=CPU_ONLY)

    assert selection.tier == "cpu"
    assert selection.device == "cpu"
    assert "none detected" in selection.reason


@pytest.mark.parametrize("preference", ["auto", "gpu", "cpu"])
def test_every_preference_yields_a_usable_bundle(preference: DevicePreference) -> None:
    selection = select_models(preference=preference, profile=BIG_GPU)

    assert selection.bundle.image.repo_id
    assert selection.bundle.image_dimensions > 0
    assert selection.bundle.text_dimensions > 0


def test_custom_vram_threshold_is_honoured() -> None:
    selection = select_models(profile=SMALL_GPU, min_vram_bytes=1024)

    assert selection.tier == "gpu"


def test_oom_downgrade_moves_to_cpu_and_explains_why() -> None:
    original = select_models(profile=BIG_GPU)

    downgraded = downgrade_to_cpu(original, "CUDA out of memory")

    assert downgraded.tier == "cpu"
    assert downgraded.device == "cpu"
    assert "downgraded from gpu tier on cuda" in downgraded.reason
    assert "CUDA out of memory" in downgraded.reason


def test_downgrade_keeps_the_detected_profile() -> None:
    original = select_models(profile=BIG_GPU)

    downgraded = downgrade_to_cpu(original, "out of memory")

    assert downgraded.profile == BIG_GPU


def test_describe_is_readable_for_the_settings_screen() -> None:
    selection = select_models(profile=CPU_ONLY)

    assert selection.describe() == "cpu tier on cpu: no GPU detected, using CPU models"


def test_both_tiers_use_chinese_aligned_image_models() -> None:
    for bundle in BUNDLES.values():
        assert "chinese-clip" in bundle.image.repo_id


def test_both_tiers_use_multilingual_text_models() -> None:
    for bundle in BUNDLES.values():
        assert "multilingual" in bundle.text.repo_id


def test_tiers_differ_in_vector_width() -> None:
    assert GPU_BUNDLE.image_dimensions != CPU_BUNDLE.image_dimensions
    assert GPU_BUNDLE.text_dimensions != CPU_BUNDLE.text_dimensions


def test_bundles_are_registered_under_their_tier() -> None:
    assert BUNDLES["gpu"].tier == "gpu"
    assert BUNDLES["cpu"].tier == "cpu"


def test_selection_defaults_to_detecting_hardware() -> None:
    assert isinstance(select_models(), ModelSelection)
