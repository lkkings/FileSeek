"""Content hashing.

Hashing is streamed so a multi-gigabyte video never lands in memory, and the
digest doubles as the dedup key.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from pathlib import Path

CHUNK_SIZE = 1024 * 1024

HASH_NAME = "sha256"


def hash_file(path: Path, chunk_size: int = CHUNK_SIZE) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def hash_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def read_and_hash(path: Path, chunk_size: int = CHUNK_SIZE) -> Iterator[tuple[bytes, str]]:
    """Yield each chunk with the running digest, so one read feeds copy and hash."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
            yield chunk, digest.hexdigest()
