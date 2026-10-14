"""jina-clip-v2 的分词：直接用 `tokenizers` 读 `tokenizer.json`，不经过 transformers。

`tokenizer.json` 自带 `truncation.max_length=77` 和 `padding=Fixed(77)`，那是 CLIP 文本塔
的老配置。transformers 调用时会用 `tokenizer_config.json` 的 `model_max_length`（8194）
覆盖掉；直接用 `tokenizers` 不会。所以加载后必须关掉 padding、把截断改成
`model_max_length`，否则长文本会被悄无声息地截到 77 个 token。
"""

from __future__ import annotations

import json
from pathlib import Path

from fileseek.shared.domain.exceptions import ModelLoadError

TOKENIZER_FILE = "tokenizer.json"
TOKENIZER_CONFIG = "tokenizer_config.json"

# 配置里没有真实上限（缺失，或是 transformers 用来表示"无限"的超大值）时用的长度。
_FALLBACK_MAX_LENGTH = 8192


class ClipTokenizer:
    """把一批文本变成 token id 列表；首尾特殊 token 由 `tokenizer.json` 的模板加。"""

    def __init__(
        self, *, tokenizer_file: Path, model_max_length: int | None, pad_token: str
    ) -> None:
        from tokenizers import Tokenizer

        self._tokenizer = Tokenizer.from_file(str(tokenizer_file))
        pad_token_id = self._tokenizer.token_to_id(pad_token)
        if pad_token_id is None:
            raise ModelLoadError(f"tokenizer 词表里没有填充符: {pad_token}")
        self.pad_token_id: int = pad_token_id
        if model_max_length is None or model_max_length > 1_000_000:
            model_max_length = _FALLBACK_MAX_LENGTH
        self.max_length: int = model_max_length
        # 只在加载时配置一次：encode_batch 可能被多个线程同时调用，不能每次去改共享状态。
        self._tokenizer.no_padding()
        self._tokenizer.enable_truncation(max_length=self.max_length)

    @classmethod
    def from_dir(cls, model_dir: Path) -> ClipTokenizer:
        tokenizer_file = model_dir / TOKENIZER_FILE
        config_path = model_dir / TOKENIZER_CONFIG
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ModelLoadError(f"无法读取 tokenizer 配置: {config_path}") from exc
        if not tokenizer_file.exists():
            raise ModelLoadError(f"缺少 tokenizer 文件: {tokenizer_file}")

        max_length = config.get("model_max_length")
        return cls(
            tokenizer_file=tokenizer_file,
            model_max_length=int(max_length) if isinstance(max_length, int | float) else None,
            pad_token=str(config.get("pad_token", "<pad>")),
        )

    def encode_batch(self, texts: list[str]) -> list[list[int]]:
        """分词并按 `max_length` 截断，不做 padding。"""
        return [encoding.ids for encoding in self._tokenizer.encode_batch(texts)]
