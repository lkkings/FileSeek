"""Tests for the runtime source-list generator."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from build_sources import model_set_id  # noqa: E402


def base_model() -> dict:
    return {
        "id": "jina-clip-v2-q",
        "repo": "jinaai/jina-clip-v2",
        "revision": "e10d47f",
        "files": [
            {
                "path": "model_quantized.onnx",
                "file": "onnx/model_quantized.onnx",
                "size": 874351078,
                "sha256": "65c6423fc82eecffb7f7f813730c6a6f0d28e2dc908e414250733b1416ed30bf",
            }
        ],
    }


def test_url_changes_do_not_change_model_set_id() -> None:
    model = base_model()
    changed = copy.deepcopy(model)
    changed["revision"] = "another-revision"
    changed["files"][0]["file"] = "another/model.onnx"

    assert model_set_id(model) == model_set_id(changed)


def test_file_hash_changes_model_set_id() -> None:
    model = base_model()
    changed = copy.deepcopy(model)
    changed["files"][0]["sha256"] = "0" * 64

    assert model_set_id(model) != model_set_id(changed)


def test_file_path_changes_model_set_id() -> None:
    model = base_model()
    changed = copy.deepcopy(model)
    changed["files"][0]["path"] = "renamed.onnx"

    assert model_set_id(model) != model_set_id(changed)


def test_file_size_changes_model_set_id() -> None:
    model = base_model()
    changed = copy.deepcopy(model)
    changed["files"][0]["size"] += 1

    assert model_set_id(model) != model_set_id(changed)
