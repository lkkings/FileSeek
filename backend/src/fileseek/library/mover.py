"""Moves a file into the managed library without ever risking the original.

Same-volume moves are a single rename. Cross-volume moves (the NAS case, where
rename is unavailable) copy to a temporary name, fsync, verify size and digest,
atomically rename into place, and only then delete the source. Every failure path
leaves the source file untouched.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

from fileseek.library.hashing import CHUNK_SIZE

PART_SUFFIX = ".fileseek-part"


class SourceMissingError(OSError):
    def __init__(self, source: Path) -> None:
        super().__init__(f"source file does not exist: {source}")
        self.source = source


class VerificationFailedError(OSError):
    """Copy completed but the destination did not match the source."""

    def __init__(self, source: Path, reason: str) -> None:
        super().__init__(f"copy verification failed for {source}: {reason}")
        self.source = source
        self.reason = reason


@dataclass(frozen=True)
class MoveResult:
    source: Path
    destination: Path
    content_hash: str
    size: int
    used_rename: bool


def _same_volume(source: Path, destination_dir: Path) -> bool:
    try:
        return source.stat().st_dev == destination_dir.stat().st_dev
    except OSError:
        return False


def _file_size(path: Path) -> int:
    return path.stat().st_size


def _verify_copy(
    source: Path, part: Path, written: int, expected_digest: str, chunk_size: int
) -> None:
    """Raise unless what landed on disk matches what was read from the source."""
    landed_size = _file_size(part)
    if landed_size != written:
        raise VerificationFailedError(
            source, f"destination size {landed_size} does not match {written} bytes copied"
        )

    # Re-read what actually landed: comparing the write-side digest against
    # itself would verify nothing.
    landed = hashlib.sha256()
    with part.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            landed.update(chunk)
    if landed.hexdigest() != expected_digest:
        raise VerificationFailedError(source, "digest mismatch between source and destination")


def _copy_verify_delete(source: Path, destination: Path, chunk_size: int) -> MoveResult:
    part = destination.with_name(destination.name + PART_SUFFIX)
    digest = hashlib.sha256()
    written = 0

    try:
        with source.open("rb") as reader, part.open("wb") as writer:
            while chunk := reader.read(chunk_size):
                digest.update(chunk)
                writer.write(chunk)
                written += len(chunk)
            writer.flush()
            os.fsync(writer.fileno())

        _verify_copy(source, part, written, digest.hexdigest(), chunk_size)
        part.replace(destination)
    except BaseException:
        part.unlink(missing_ok=True)
        raise

    source.unlink()
    return MoveResult(
        source=source,
        destination=destination,
        content_hash=digest.hexdigest(),
        size=written,
        used_rename=False,
    )


def move_into_library(
    source: Path,
    destination: Path,
    chunk_size: int = CHUNK_SIZE,
    known_hash: str | None = None,
) -> MoveResult:
    """Move source to destination, returning the content hash computed en route."""
    if not source.is_file():
        raise SourceMissingError(source)

    destination.parent.mkdir(parents=True, exist_ok=True)

    if _same_volume(source, destination.parent):
        size = source.stat().st_size
        # Hash before the rename: afterwards the source path is gone.
        content_hash = known_hash if known_hash is not None else _hash(source, chunk_size)
        source.rename(destination)
        return MoveResult(
            source=source,
            destination=destination,
            content_hash=content_hash,
            size=size,
            used_rename=True,
        )

    return _copy_verify_delete(source, destination, chunk_size)


def _hash(path: Path, chunk_size: int) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def cleanup_orphan_parts(*directories: Path) -> list[Path]:
    """Delete leftover `.fileseek-part` files from interrupted copies."""
    removed: list[Path] = []
    for directory in directories:
        if not directory.is_dir():
            continue
        for candidate in directory.rglob(f"*{PART_SUFFIX}"):
            if not candidate.is_file():
                continue
            try:
                candidate.unlink()
            except OSError:
                continue
            removed.append(candidate)
    return removed
