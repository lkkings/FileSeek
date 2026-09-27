from __future__ import annotations

from typing import Protocol


class EmbeddingPort(Protocol):
    """文本/图片向量化。

    两个方法**都返回一批**：`list[list[float]]`，外层一条对应一个输入。传单个 `str`/`bytes`
    拿回来的也是 `[[...]]`，调用方要自己取 `[0]`。

    这里之前写的是 `list[float] | list[list[float]]`。那个联合类型是个陷阱：它让"单条返回
    裸向量、多条返回批"看起来也合法，于是真实现（永远返回批）和测试里的假实现（单条返回
    裸向量）各按一种理解走，静态检查两边都放过。结果是四个调用方把批当成单条向量存进
    向量库，Chroma 报 "Expected embeddings to be a list of floats or ints ... got [[["，
    而单元测试全绿。
    """

    def embed_text(
        self, texts: str | list[str], *, query: bool = False
    ) -> list[list[float]]: ...
    def embed_image(self, images: bytes | list[bytes]) -> list[list[float]]: ...
