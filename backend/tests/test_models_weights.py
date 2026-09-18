from collections.abc import Iterator
from pathlib import Path

import pytest

from fileseek.library.hashing import hash_bytes
from fileseek.models.tiers import CPU_BUNDLE, GPU_BUNDLE
from fileseek.models.weights import (
    MARKER_SUFFIX,
    PART_SUFFIX,
    ConsentRequiredError,
    DigestMismatchError,
    WeightDownloader,
    WeightStore,
)

PAYLOAD = b"pretend these are model weights"
DIGEST = hash_bytes(PAYLOAD)

IMAGE_REPO = CPU_BUNDLE.image.repo_id


@pytest.fixture
def store(tmp_path: Path) -> WeightStore:
    return WeightStore(tmp_path / "models")


def whole_file_fetcher(payload: bytes = PAYLOAD, chunk: int = 8) -> object:
    def fetch(repo_id: str, offset: int) -> Iterator[bytes]:
        remaining = payload[offset:]
        for start in range(0, len(remaining), chunk):
            yield remaining[start : start + chunk]

    return fetch


def test_missing_weights_are_reported_absent(store: WeightStore) -> None:
    status = store.status_for(IMAGE_REPO)

    assert status.is_present is False
    assert status.repo_id == IMAGE_REPO


def test_status_name_strips_the_org_prefix(store: WeightStore) -> None:
    assert store.status_for("OFA-Sys/chinese-clip-vit-base-patch16").name == (
        "chinese-clip-vit-base-patch16"
    )


def test_path_for_avoids_nested_directories(store: WeightStore) -> None:
    assert store.path_for("org/model").parent == store.root


def test_tier_is_not_ready_until_every_weight_is_present(store: WeightStore) -> None:
    readiness = store.readiness(CPU_BUNDLE)

    assert readiness.is_ready is False
    # The OCR model ships with its package, so only the two fetched models are missing.
    assert len(readiness.missing) == 2
    assert "missing weights" in readiness.describe()


def test_tier_becomes_ready_once_all_weights_verified(store: WeightStore, tmp_path: Path) -> None:
    source = tmp_path / "incoming.bin"
    source.write_bytes(PAYLOAD)
    for spec in (CPU_BUNDLE.image, CPU_BUNDLE.text, CPU_BUNDLE.ocr):
        store.install_from(spec.repo_id, source)

    readiness = store.readiness(CPU_BUNDLE)

    assert readiness.is_ready is True
    assert readiness.missing == ()
    assert readiness.describe() == "cpu tier is ready"


def test_partial_tier_is_still_not_ready(store: WeightStore, tmp_path: Path) -> None:
    source = tmp_path / "incoming.bin"
    source.write_bytes(PAYLOAD)
    store.install_from(CPU_BUNDLE.image.repo_id, source)

    assert store.readiness(CPU_BUNDLE).is_ready is False


def test_readiness_for_tier_looks_up_the_bundle(store: WeightStore) -> None:
    assert store.readiness_for_tier("gpu").tier == "gpu"
    assert store.readiness_for_tier("cpu").tier == "cpu"


def test_tiers_track_readiness_independently(store: WeightStore, tmp_path: Path) -> None:
    source = tmp_path / "incoming.bin"
    source.write_bytes(PAYLOAD)
    for spec in (CPU_BUNDLE.image, CPU_BUNDLE.text, CPU_BUNDLE.ocr):
        store.install_from(spec.repo_id, source)

    assert store.readiness(CPU_BUNDLE).is_ready is True
    assert store.readiness(GPU_BUNDLE).is_ready is False


def snapshot(store: WeightStore, repo_id: str, *, weights: str = "model.safetensors") -> Path:
    """Mimic a snapshot download: a directory of files, with no digest marker."""
    target = store.path_for(repo_id)
    target.mkdir(parents=True, exist_ok=True)
    (target / "config.json").write_text("{}", encoding="utf-8")
    (target / weights).write_bytes(PAYLOAD)
    return target


def test_snapshot_directory_counts_as_present(store: WeightStore) -> None:
    """A real download leaves a directory of files, not one verified payload."""
    snapshot(store, IMAGE_REPO)

    assert store.is_present(IMAGE_REPO) is True


@pytest.mark.parametrize("weights", ["model.safetensors", "pytorch_model.bin", "model.onnx"])
def test_each_weight_file_shape_is_recognised(store: WeightStore, weights: str) -> None:
    snapshot(store, IMAGE_REPO, weights=weights)

    assert store.is_present(IMAGE_REPO) is True


def test_directory_without_weight_files_is_not_present(store: WeightStore) -> None:
    """The first download attempt fetched only tokenizer files; that is not usable."""
    target = store.path_for(IMAGE_REPO)
    (target / "onnx").mkdir(parents=True)
    (target / "onnx" / "tokenizer.json").write_text("{}", encoding="utf-8")

    assert store.is_present(IMAGE_REPO) is False


def test_interrupted_snapshot_is_not_present(store: WeightStore) -> None:
    target = snapshot(store, IMAGE_REPO)
    (target / "model.safetensors.incomplete").write_bytes(b"partial")

    assert store.is_present(IMAGE_REPO) is False


def test_snapshot_in_a_nested_directory_is_found(store: WeightStore) -> None:
    target = store.path_for(IMAGE_REPO)
    (target / "nested").mkdir(parents=True)
    (target / "nested" / "model.safetensors").write_bytes(PAYLOAD)

    assert store.is_present(IMAGE_REPO) is True


def test_bundled_model_needs_no_download(store: WeightStore) -> None:
    """RapidOCR ships its ONNX files inside the pip package, so nothing is fetched."""
    assert store.is_present("rapidocr-onnxruntime", bundled=True) is True
    assert store.status_for("rapidocr-onnxruntime", bundled=True).is_present is True


def test_tier_is_ready_once_snapshots_land(store: WeightStore) -> None:
    snapshot(store, CPU_BUNDLE.image.repo_id)
    snapshot(store, CPU_BUNDLE.text.repo_id)

    readiness = store.readiness(CPU_BUNDLE)

    assert readiness.is_ready is True
    assert readiness.describe() == "cpu tier is ready"


def test_bundled_ocr_is_not_reported_missing(store: WeightStore) -> None:
    missing = {status.repo_id for status in store.readiness(CPU_BUNDLE).missing}

    assert CPU_BUNDLE.ocr.repo_id not in missing


def test_download_bundle_skips_bundled_models(store: WeightStore) -> None:
    downloader = WeightDownloader(store, whole_file_fetcher())  # type: ignore[arg-type]

    installed = downloader.download_bundle(CPU_BUNDLE, consent=True)

    assert len(installed) == 2


def test_unverified_payload_does_not_count_as_present(store: WeightStore) -> None:
    """A file without its digest marker was never verified, so it is not usable."""
    target = store.path_for(IMAGE_REPO)
    target.parent.mkdir(parents=True)
    target.write_bytes(PAYLOAD)

    assert store.is_present(IMAGE_REPO) is False


def test_install_from_records_the_digest(store: WeightStore, tmp_path: Path) -> None:
    source = tmp_path / "incoming.bin"
    source.write_bytes(PAYLOAD)

    installed = store.install_from(IMAGE_REPO, source)

    assert installed.read_bytes() == PAYLOAD
    assert store.is_present(IMAGE_REPO) is True
    assert store.verified_digest(IMAGE_REPO) == DIGEST


def test_install_from_verifies_an_expected_digest(store: WeightStore, tmp_path: Path) -> None:
    source = tmp_path / "incoming.bin"
    source.write_bytes(PAYLOAD)

    with pytest.raises(DigestMismatchError, match="failed verification") as excinfo:
        store.install_from(IMAGE_REPO, source, expected_digest="0" * 64)

    assert excinfo.value.actual == DIGEST
    assert store.is_present(IMAGE_REPO) is False


def test_offline_bundle_can_be_installed_by_hand(store: WeightStore, tmp_path: Path) -> None:
    source = tmp_path / "offline" / "weights.bin"
    source.parent.mkdir()
    source.write_bytes(PAYLOAD)

    store.install_from(IMAGE_REPO, source, expected_digest=DIGEST)

    assert store.is_present(IMAGE_REPO) is True


def test_verified_digest_is_none_when_absent(store: WeightStore) -> None:
    assert store.verified_digest(IMAGE_REPO) is None


def test_remove_deletes_payload_and_marker(store: WeightStore, tmp_path: Path) -> None:
    source = tmp_path / "incoming.bin"
    source.write_bytes(PAYLOAD)
    store.install_from(IMAGE_REPO, source)

    assert store.remove(IMAGE_REPO) is True
    assert store.is_present(IMAGE_REPO) is False
    assert store.verified_digest(IMAGE_REPO) is None


def test_remove_reports_false_when_nothing_present(store: WeightStore) -> None:
    assert store.remove(IMAGE_REPO) is False


def test_remove_handles_a_directory_payload(store: WeightStore) -> None:
    target = store.path_for(IMAGE_REPO)
    target.mkdir(parents=True)
    (target / "config.json").write_text("{}", encoding="utf-8")

    assert store.remove(IMAGE_REPO) is True
    assert not target.exists()


def test_download_requires_consent(store: WeightStore) -> None:
    downloader = WeightDownloader(store, whole_file_fetcher())  # type: ignore[arg-type]

    with pytest.raises(ConsentRequiredError, match="requires user consent"):
        downloader.download(IMAGE_REPO)

    assert store.is_present(IMAGE_REPO) is False


def test_download_with_consent_installs_and_verifies(store: WeightStore) -> None:
    downloader = WeightDownloader(
        store,
        whole_file_fetcher(),
        expected_digests={IMAGE_REPO: DIGEST},  # type: ignore[arg-type]
    )

    installed = downloader.download(IMAGE_REPO, consent=True)

    assert installed.read_bytes() == PAYLOAD
    assert store.is_present(IMAGE_REPO) is True


def test_download_reports_progress(store: WeightStore) -> None:
    seen: list[int] = []
    downloader = WeightDownloader(store, whole_file_fetcher(chunk=8))  # type: ignore[arg-type]

    downloader.download(IMAGE_REPO, consent=True, on_progress=lambda _, total: seen.append(total))

    assert seen == sorted(seen)
    assert seen[-1] == len(PAYLOAD)


def test_download_leaves_no_part_file(store: WeightStore) -> None:
    downloader = WeightDownloader(store, whole_file_fetcher())  # type: ignore[arg-type]

    downloader.download(IMAGE_REPO, consent=True)

    assert list(store.root.glob(f"*{PART_SUFFIX}")) == []


def test_download_resumes_from_a_partial_file(store: WeightStore) -> None:
    target = store.path_for(IMAGE_REPO)
    target.parent.mkdir(parents=True)
    part = target.with_name(target.name + PART_SUFFIX)
    part.write_bytes(PAYLOAD[:10])
    offsets: list[int] = []

    def fetch(repo_id: str, offset: int) -> Iterator[bytes]:
        offsets.append(offset)
        yield PAYLOAD[offset:]

    downloader = WeightDownloader(store, fetch)  # type: ignore[arg-type]
    downloader.download(IMAGE_REPO, consent=True)

    assert offsets == [10]
    assert target.read_bytes() == PAYLOAD


def test_bad_digest_is_discarded_rather_than_installed(store: WeightStore) -> None:
    downloader = WeightDownloader(
        store,
        whole_file_fetcher(),
        expected_digests={IMAGE_REPO: "0" * 64},  # type: ignore[arg-type]
    )

    with pytest.raises(DigestMismatchError):
        downloader.download(IMAGE_REPO, consent=True)

    assert store.is_present(IMAGE_REPO) is False
    assert list(store.root.glob(f"*{PART_SUFFIX}")) == []


def test_download_without_expected_digest_still_records_one(store: WeightStore) -> None:
    downloader = WeightDownloader(store, whole_file_fetcher())  # type: ignore[arg-type]

    downloader.download(IMAGE_REPO, consent=True)

    assert store.verified_digest(IMAGE_REPO) == DIGEST


def test_download_bundle_fetches_every_missing_weight(store: WeightStore) -> None:
    downloader = WeightDownloader(store, whole_file_fetcher())  # type: ignore[arg-type]

    installed = downloader.download_bundle(CPU_BUNDLE, consent=True)

    assert len(installed) == 2
    assert store.readiness(CPU_BUNDLE).is_ready is True


def test_download_bundle_skips_present_weights(store: WeightStore, tmp_path: Path) -> None:
    source = tmp_path / "incoming.bin"
    source.write_bytes(PAYLOAD)
    store.install_from(CPU_BUNDLE.image.repo_id, source)
    downloader = WeightDownloader(store, whole_file_fetcher())  # type: ignore[arg-type]

    installed = downloader.download_bundle(CPU_BUNDLE, consent=True)

    assert len(installed) == 1


def test_download_bundle_requires_consent(store: WeightStore) -> None:
    downloader = WeightDownloader(store, whole_file_fetcher())  # type: ignore[arg-type]

    with pytest.raises(ConsentRequiredError):
        downloader.download_bundle(CPU_BUNDLE)


def test_marker_files_sit_beside_their_payload(store: WeightStore, tmp_path: Path) -> None:
    source = tmp_path / "incoming.bin"
    source.write_bytes(PAYLOAD)

    store.install_from(IMAGE_REPO, source)

    target = store.path_for(IMAGE_REPO)
    assert target.with_name(target.name + MARKER_SUFFIX).is_file()
