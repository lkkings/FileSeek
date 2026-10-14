"""`runtime_id` must match the Rust implementation."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime_id import compute_runtime_id  # noqa: E402


def test_matches_the_rust_implementation() -> None:
    assert (
        compute_runtime_id(b"version = 1\n[[package]]\n", "3.12.15", "20261001")
        == "rt-d33d847dcabf2a87"
    )


def test_crlf_and_lf_lockfiles_get_the_same_id() -> None:
    assert compute_runtime_id(b"a\r\nb\r\n", "3.12.15", "20261001") == compute_runtime_id(
        b"a\nb\n", "3.12.15", "20261001"
    )


def test_dependency_change_changes_the_id() -> None:
    assert compute_runtime_id(b"torch==2.14.0", "3.12.15", "20261001") != compute_runtime_id(
        b"torch==2.15.0", "3.12.15", "20261001"
    )
