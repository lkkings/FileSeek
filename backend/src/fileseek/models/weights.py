"""Tracks which model weights are on disk, and fetches missing ones on consent.

Weights are not bundled: the installer would reach gigabytes while any one machine
uses a single tier. So the app ships a fetcher, and until a tier's weights are
present it must not claim indexing is available.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

from fileseek.library.hashing import hash_file
from fileseek.models.tiers import BUNDLES, ModelBundle, ModelTier

PART_SUFFIX = ".part"

# A marker beside the payload records the digest that was verified on arrival.
MARKER_SUFFIX = ".sha256"

# A snapshot download leaves a directory of files rather than one payload, so it
# is judged by whether real weights arrived and nothing is still partial.
WEIGHT_FILE_SUFFIXES = frozenset({".safetensors", ".bin", ".onnx", ".pt", ".model"})

INCOMPLETE_SUFFIX = ".incomplete"


class ConsentRequiredError(RuntimeError):
    """Downloading needs explicit user agreement; it is the only outbound traffic."""

    def __init__(self, repo_id: str) -> None:
        super().__init__(f"downloading {repo_id} requires user consent")
        self.repo_id = repo_id


class DigestMismatchError(RuntimeError):
    def __init__(self, repo_id: str, expected: str, actual: str) -> None:
        super().__init__(
            f"weights for {repo_id} failed verification: expected {expected}, got {actual}"
        )
        self.repo_id = repo_id
        self.expected = expected
        self.actual = actual


@dataclass(frozen=True)
class WeightStatus:
    repo_id: str
    path: Path
    is_present: bool

    @property
    def name(self) -> str:
        return self.repo_id.rsplit("/", maxsplit=1)[-1]


@dataclass(frozen=True)
class TierReadiness:
    """Whether a tier can index yet, and what is still missing if not."""

    tier: ModelTier
    statuses: tuple[WeightStatus, ...]

    @property
    def is_ready(self) -> bool:
        return all(status.is_present for status in self.statuses)

    @property
    def missing(self) -> tuple[WeightStatus, ...]:
        return tuple(status for status in self.statuses if not status.is_present)

    def describe(self) -> str:
        if self.is_ready:
            return f"{self.tier} tier is ready"
        names = ", ".join(status.name for status in self.missing)
        return f"{self.tier} tier is missing weights: {names}"


def _slug(repo_id: str) -> str:
    return repo_id.replace("/", "--")


def _has_weight_files(directory: Path) -> bool:
    return any(
        entry.suffix.lower() in WEIGHT_FILE_SUFFIXES
        for entry in directory.rglob("*")
        if entry.is_file()
    )


def _has_partial_files(directory: Path) -> bool:
    return any(directory.rglob(f"*{INCOMPLETE_SUFFIX}"))


class WeightStore:
    """Where weights live on disk, and how they get there."""

    def __init__(self, root: Path) -> None:
        self._root = root

    @property
    def root(self) -> Path:
        return self._root

    def path_for(self, repo_id: str) -> Path:
        return self._root / _slug(repo_id)

    def is_present(self, repo_id: str, bundled: bool = False) -> bool:
        """Whether these weights are on disk and usable.

        Two shapes arrive in practice: a single verified payload, marked with its
        digest, and a snapshot directory of many files, judged by whether real
        weights landed and nothing is still partial.
        """
        if bundled:
            return True

        target = self.path_for(repo_id)
        if target.is_dir():
            return _has_weight_files(target) and not _has_partial_files(target)
        if not target.exists():
            return False
        marker = target.with_name(target.name + MARKER_SUFFIX)
        return marker.is_file()

    def status_for(self, repo_id: str, bundled: bool = False) -> WeightStatus:
        return WeightStatus(
            repo_id=repo_id,
            path=self.path_for(repo_id),
            is_present=self.is_present(repo_id, bundled),
        )

    def readiness(self, bundle: ModelBundle) -> TierReadiness:
        return TierReadiness(
            tier=bundle.tier,
            statuses=tuple(
                self.status_for(spec.repo_id, spec.bundled)
                for spec in (bundle.image, bundle.text, bundle.ocr)
            ),
        )

    def readiness_for_tier(self, tier: ModelTier) -> TierReadiness:
        return self.readiness(BUNDLES[tier])

    def record_verified(self, repo_id: str, digest: str) -> None:
        target = self.path_for(repo_id)
        target.with_name(target.name + MARKER_SUFFIX).write_text(digest, encoding="utf-8")

    def verified_digest(self, repo_id: str) -> str | None:
        marker = self.path_for(repo_id)
        marker = marker.with_name(marker.name + MARKER_SUFFIX)
        if not marker.is_file():
            return None
        return marker.read_text(encoding="utf-8").strip()

    def install_from(self, repo_id: str, source: Path, expected_digest: str | None = None) -> Path:
        """Adopt an already-downloaded file, e.g. from an offline weights bundle."""
        digest = hash_file(source)
        if expected_digest is not None and digest != expected_digest:
            raise DigestMismatchError(repo_id, expected_digest, digest)

        target = self.path_for(repo_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        self.record_verified(repo_id, digest)
        return target

    def remove(self, repo_id: str) -> bool:
        target = self.path_for(repo_id)
        marker = target.with_name(target.name + MARKER_SUFFIX)
        existed = target.exists()
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink(missing_ok=True)
        marker.unlink(missing_ok=True)
        return existed


# A fetcher yields chunks so a large download can resume and report progress.
Fetcher = Callable[[str, int], Iterator[bytes]]

ProgressCallback = Callable[[str, int], None]


class WeightDownloader:
    def __init__(
        self,
        store: WeightStore,
        fetcher: Fetcher,
        expected_digests: dict[str, str] | None = None,
    ) -> None:
        self._store = store
        self._fetcher = fetcher
        self._expected = expected_digests or {}

    def download(
        self,
        repo_id: str,
        consent: bool = False,
        on_progress: ProgressCallback | None = None,
    ) -> Path:
        """Fetch one repo's weights, resuming a partial file if one is present."""
        if not consent:
            raise ConsentRequiredError(repo_id)

        target = self._store.path_for(repo_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        part = target.with_name(target.name + PART_SUFFIX)

        # Resume from whatever a previous attempt managed to write.
        already = part.stat().st_size if part.is_file() else 0
        with part.open("ab") as handle:
            for chunk in self._fetcher(repo_id, already):
                handle.write(chunk)
                already += len(chunk)
                if on_progress is not None:
                    on_progress(repo_id, already)

        digest = hash_file(part)
        expected = self._expected.get(repo_id)
        if expected is not None and digest != expected:
            # Keep nothing unverified: a bad payload must not look installed.
            part.unlink(missing_ok=True)
            raise DigestMismatchError(repo_id, expected, digest)

        part.replace(target)
        self._store.record_verified(repo_id, digest)
        return target

    def download_bundle(
        self,
        bundle: ModelBundle,
        consent: bool = False,
        on_progress: ProgressCallback | None = None,
    ) -> list[Path]:
        """Fetch whatever the tier is missing, skipping what is already present.

        A bundled model ships with its pip package, so there is nothing to fetch.
        """
        installed: list[Path] = []
        for spec in (bundle.image, bundle.text, bundle.ocr):
            if spec.bundled or self._store.is_present(spec.repo_id, spec.bundled):
                continue
            installed.append(self.download(spec.repo_id, consent=consent, on_progress=on_progress))
        return installed
