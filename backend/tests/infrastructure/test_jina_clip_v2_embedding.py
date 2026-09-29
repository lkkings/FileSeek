import numpy as np

from fileseek.infrastructure.embedding import jina_clip_v2
from fileseek.infrastructure.embedding.jina_clip_v2 import JinaClipV2Embedding


def _make_embedding(token_ids: dict[str, list[int]], batches: list[np.ndarray]):
    """构造一个不加载模型的实例，tokenizer 按映射返回 token ids。"""
    embedding = object.__new__(JinaClipV2Embedding)

    def tokenizer(texts: list[str], **_: object):
        return {"input_ids": [token_ids[text] for text in texts]}

    def run_text_inference(*, session, input_ids):
        batches.append(input_ids)
        # 用每行第一个 token 作为"向量"，方便校验顺序是否还原。
        return input_ids[:, :1]

    embedding._ensure_loaded = lambda: (object(), tokenizer, object())
    embedding._run_text_inference = run_text_inference
    embedding._to_embedding_list = lambda outputs: outputs.tolist()
    embedding._get_max_sequence_length = lambda tokenizer: 8192
    return embedding


def test_text_inference_is_split_into_fixed_batches(monkeypatch):
    monkeypatch.setattr(jina_clip_v2, "TEXT_INFERENCE_BATCH_SIZE", 4)
    batches: list[np.ndarray] = []
    texts = [str(index) for index in range(9)]
    embedding = _make_embedding({text: [int(text)] for text in texts}, batches)

    embeddings = embedding.embed_text(texts)

    assert [len(batch) for batch in batches] == [4, 4, 1]
    assert embeddings == [[0], [1], [2], [3], [4], [5], [6], [7], [8]]


def test_long_text_is_not_batched_with_short_texts(monkeypatch):
    # 预算只够 1 条 100 token，或 4 条 10 token。
    monkeypatch.setattr(jina_clip_v2, "TEXT_INFERENCE_MAX_ATTENTION_COST", 100 * 100)
    batches: list[np.ndarray] = []
    token_ids = {"long": [9] * 100}
    token_ids.update({f"short{index}": [index] * 10 for index in range(4)})
    embedding = _make_embedding(token_ids, batches)

    embeddings = embedding.embed_text(["short0", "long", "short1", "short2", "short3"])

    # 长文本独占一批，短文本只 padding 到 10，而不是 100。
    assert [batch.shape for batch in batches] == [(1, 100), (4, 10)]
    assert embeddings == [[0], [9], [1], [2], [3]]


def test_batch_is_padded_with_pad_token_id():
    input_ids = JinaClipV2Embedding._pad_token_ids([[5, 6, 7], [8]], pad_token_id=1)

    assert input_ids.dtype == np.int64
    assert input_ids.tolist() == [[5, 6, 7], [8, 1, 1]]
