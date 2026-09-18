import hashlib
from pathlib import Path

from fileseek.library.hashing import hash_bytes, hash_file, read_and_hash

KNOWN_TEXT = b"the quick brown fox"
KNOWN_DIGEST = "9ecb36561341d18eb65484e833efea61edc74b84cf5e6ae1b81c63533e25fc8f"


def test_hash_of_known_bytes_matches_reference() -> None:
    assert hash_bytes(KNOWN_TEXT) == KNOWN_DIGEST


def test_hash_file_matches_reference_digest(tmp_path: Path) -> None:
    target = tmp_path / "sample.txt"
    target.write_bytes(KNOWN_TEXT)

    assert hash_file(target) == KNOWN_DIGEST


def test_hash_file_matches_hashlib_for_large_content(tmp_path: Path) -> None:
    payload = bytes(range(256)) * 20_000
    target = tmp_path / "large.bin"
    target.write_bytes(payload)

    assert hash_file(target) == hashlib.sha256(payload).hexdigest()


def test_small_chunk_size_gives_same_digest(tmp_path: Path) -> None:
    payload = b"a" * 5000
    target = tmp_path / "chunky.bin"
    target.write_bytes(payload)

    assert hash_file(target, chunk_size=7) == hashlib.sha256(payload).hexdigest()


def test_empty_file_hashes_to_empty_digest(tmp_path: Path) -> None:
    target = tmp_path / "empty.bin"
    target.touch()

    assert hash_file(target) == hashlib.sha256(b"").hexdigest()


def test_read_and_hash_yields_chunks_and_final_digest(tmp_path: Path) -> None:
    payload = b"0123456789"
    target = tmp_path / "stream.bin"
    target.write_bytes(payload)

    pairs = list(read_and_hash(target, chunk_size=4))

    assert b"".join(chunk for chunk, _ in pairs) == payload
    assert pairs[-1][1] == hashlib.sha256(payload).hexdigest()


def test_read_and_hash_on_empty_file_yields_nothing(tmp_path: Path) -> None:
    target = tmp_path / "empty.bin"
    target.touch()

    assert list(read_and_hash(target)) == []
