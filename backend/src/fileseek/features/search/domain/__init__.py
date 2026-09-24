"""Search feature 领域层。

检索用的端口（嵌入、向量库）定义在 tasks 侧的 `domain/ports/file_processor.py`：写入和
读取必须共用一份契约，否则索引时落的元数据字段和检索时读的字段会各写一套、悄悄错位。
"""

from fileseek.features.search.domain.entities import SearchFileMetadata, SearchResult

__all__ = [
    "SearchFileMetadata",
    "SearchResult",
]
