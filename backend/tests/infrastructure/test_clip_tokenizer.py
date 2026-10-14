"""分词与旧实现（transformers `AutoTokenizer`）的对照。

基准由 `scripts/make_parity_fixtures.py` 在旧依赖下生成。需要真实的 `tokenizer.json`
（17MB，不进仓库），所以只在本地缓存了模型时运行。
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from fileseek.infrastructure.embedding.clip_tokenizer import ClipTokenizer
from fileseek.shared.domain.exceptions import ModelLoadError

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "parity"
TOKENIZER_DIR = Path.home() / ".cache" / "fileseek" / "models" / "tokenizer"
needs_tokenizer = pytest.mark.skipif(
    not (TOKENIZER_DIR / "tokenizer.json").exists(),
    reason="需要本地已缓存的 jina-clip-v2 tokenizer",
)


@needs_tokenizer
def test_token_ids_match_previous_implementation() -> None:
    records = json.loads((FIXTURES / "token_ids.json").read_text(encoding="utf-8"))
    tokenizer = ClipTokenizer.from_dir(TOKENIZER_DIR)

    actual = tokenizer.encode_batch([record["text"] for record in records])

    for record, ids in zip(records, actual, strict=True):
        assert ids == record["input_ids"], record["text"][:40]


@needs_tokenizer
def test_long_text_is_not_truncated_to_tokenizer_json_default() -> None:
    # tokenizer.json 自带截断到 77；没覆盖掉的话这里会是 77。
    tokenizer = ClipTokenizer.from_dir(TOKENIZER_DIR)

    (ids,) = tokenizer.encode_batch([" ".join(["semantic"] * 300)])

    assert len(ids) > 77
    assert tokenizer.max_length == 8194
    assert tokenizer.pad_token_id == 1


@needs_tokenizer
def test_truncates_at_model_max_length() -> None:
    tokenizer = ClipTokenizer.from_dir(TOKENIZER_DIR)

    (ids,) = tokenizer.encode_batch([" ".join(["检索"] * 20000)])

    assert len(ids) == 8194
    assert ids[0] == 0  # <s>
    assert ids[-1] == 2  # </s>


@needs_tokenizer
@pytest.mark.parametrize("max_length", [None, 10**30])
def test_unbounded_max_length_falls_back(max_length: int | None, tmp_path: Path) -> None:
    shutil.copy(TOKENIZER_DIR / "tokenizer.json", tmp_path / "tokenizer.json")
    config = {"pad_token": "<pad>"}
    if max_length is not None:
        config["model_max_length"] = max_length  # type: ignore[assignment]
    (tmp_path / "tokenizer_config.json").write_text(json.dumps(config), encoding="utf-8")

    assert ClipTokenizer.from_dir(tmp_path).max_length == 8192


def test_missing_files_fail_at_load(tmp_path: Path) -> None:
    with pytest.raises(ModelLoadError):
        ClipTokenizer.from_dir(tmp_path)

    (tmp_path / "tokenizer_config.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ModelLoadError):
        ClipTokenizer.from_dir(tmp_path)
