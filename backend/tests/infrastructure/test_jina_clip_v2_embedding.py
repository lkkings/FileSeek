import numpy as np

from fileseek.infrastructure.embedding.jina_clip_v2 import JinaClipV2Embedding


def _make_embedding(token_ids: dict[str, list[int]], batches: list[np.ndarray]):
    """构造一个不加载模型的实例，tokenizer 按映射返回 token ids。"""
    embedding = object.__new__(JinaClipV2Embedding)

    class Tokenizer:
        pad_token_id = 1

        def encode_batch(self, texts: list[str]) -> list[list[int]]:
            return [token_ids[text] for text in texts]

    tokenizer = Tokenizer()

    def run_text_inference(*, session, input_ids):
        batches.append(input_ids)
        # 用每行第一个 token 作为"向量"，方便校验顺序是否还原。
        return input_ids[:, :1]

    embedding._ensure_loaded = lambda: (object(), tokenizer, object())
    embedding._run_text_inference = run_text_inference
    embedding._to_embedding_list = lambda outputs: outputs.tolist()
    return embedding


def test_text_inference_submits_one_item_at_a_time():
    batches: list[np.ndarray] = []
    token_ids = {"short": [5], "long": [6, 7, 8]}
    embedding = _make_embedding(token_ids, batches)

    embeddings = embedding.embed_text(["short", "long"])

    assert [batch.tolist() for batch in batches] == [[[5]], [[6, 7, 8]]]
    assert embeddings == [[5], [6]]


def test_image_inference_submits_one_item_at_a_time_and_preserves_order():
    pixel_batches: list[np.ndarray] = []
    embedding = object.__new__(JinaClipV2Embedding)
    embedding._text_only = False

    class ImageProcessor:
        def __call__(self, images: list[bytes]) -> np.ndarray:
            return np.asarray([[float(image[0])] for image in images], dtype=np.float32)

    def run_image_inference(*, session, pixel_values):
        pixel_batches.append(pixel_values.copy())
        return np.asarray([[float(pixel_values[0, 0])]], dtype=np.float32)

    embedding._ensure_loaded = lambda: (object(), object(), ImageProcessor())
    embedding._load_image = lambda image: image
    embedding._run_image_inference = run_image_inference

    embeddings = embedding.embed_image([b"alpha", b"beta"])

    assert [batch.tolist() for batch in pixel_batches] == [[[97.0]], [[98.0]]]
    assert embeddings == [[97.0], [98.0]]
