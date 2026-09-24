"""ChromaDB 向量存储实现。

使用 ChromaDB 存储和检索文档、图片、视频的向量表示。
每条向量都携带完整的文件元信息（名称、路径、体积、修改时间），检索因此不必回库表：
一次 query 就能拿到渲染搜索结果所需的全部字段，高级筛选也能直接下推到这里执行。
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from fileseek.features.tasks.domain.ports import (
    IndexedFileMetadata,
    VectorHit,
    VectorIndexPort,
    VectorSearchFilters,
)
from fileseek.shared.domain.file_types import FileType

# 超量取回倍数。两处需要它：名称子串筛选（Chroma 没有子串算子，只能查回来再筛，
# 被筛掉多少事先不知道），以及连续片段合并（合并只减少条数，只取 limit 条会不够）。
_OVERFETCH_FACTOR = 10
# 元数据里的文本字段截断长度，避免元数据过大。
_TEXT_LIMIT = 500

# 向量对应文件内不同**位置**、因而可以按相邻合并的类型。
# 文档靠 chunk_index 连号判断相邻，视频靠关键帧在时间轴上首尾相接。
# 图片不在其中：它的两条向量是同一张图的两个侧面（OCR 文本、视觉特征），
# 不是两个位置，所以走 `_best_per_file` 只留分数最高的那条。
_MERGEABLE_TYPES = frozenset({FileType.DOCUMENT, FileType.VIDEO})

# 判定两个视频关键帧相接的时间容差（秒）。采样得到的起止时间是浮点数，
# 前一段的 end_time 和后一段的 start_time 往往差着极小的量，
# 严格相等会漏判。
_VIDEO_ADJACENCY_TOLERANCE = 0.001

# 文档分块时块间的重叠字符数上限（见 DocumentParser.parse_and_chunk 的 overlap 参数）。
# 拼接相邻块时要去掉这段重复，否则合并出的正文里有一截读两遍。
_MAX_CHUNK_OVERLAP = 50


def _iso_to_ts(value: str | None) -> float | None:
    """ISO 时间串转 epoch 秒。无法解析时返回 None（不阻断索引或检索）。"""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).timestamp()
    except ValueError:
        return None


def _base_metadata(metadata: IndexedFileMetadata) -> dict[str, Any]:
    """每条向量共用的文件级元信息。

    Chroma 的元数据值不接受 None，缺失的字段直接不写键；读回来时用 `.get` 补 None。
    """
    fields: dict[str, Any] = {
        "file_id": metadata.file_id,
        "file_name": metadata.file_name,
        # 名称筛选是大小写不敏感的子串匹配，预存小写副本省掉每次比较时的转换。
        "file_name_lower": metadata.file_name.lower(),
        "path": metadata.path,
        "accessible": metadata.accessible,
    }
    if metadata.size is not None:
        fields["size"] = metadata.size
    if metadata.modified is not None:
        fields["modified"] = metadata.modified
    if metadata.modified_ts is not None:
        fields["modified_ts"] = metadata.modified_ts
    return fields


class ChromaVectorStore(VectorIndexPort):
    """ChromaDB 向量存储适配器。"""

    def __init__(self, persist_directory: Path) -> None:
        """初始化 ChromaDB 客户端。

        Args:
            persist_directory: 向量数据库持久化目录
        """
        persist_directory.mkdir(parents=True, exist_ok=True)
        # 必须是 PersistentClient：`chromadb.Client` 在 1.x 是内存客户端，
        # 它会忽略 persist_directory（写入进程退出即失），而且同一进程里共享一个
        # system——第二个指向别的目录的实例会直接报 "already exists with different
        # settings"。PersistentClient 按 path 隔离，重开同一目录能读回既有数据。
        self._client = chromadb.PersistentClient(
            path=str(persist_directory),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        # 为不同媒体类型创建独立的 collection
        self._doc_collection = self._client.get_or_create_collection(
            name="documents",
            metadata={"description": "文档文本块向量"},
        )
        self._img_collection = self._client.get_or_create_collection(
            name="images",
            metadata={"description": "图片特征向量（OCR+视觉）"},
        )
        self._video_collection = self._client.get_or_create_collection(
            name="videos",
            metadata={"description": "视频关键帧向量"},
        )
        self._collections = {
            FileType.DOCUMENT: self._doc_collection,
            FileType.IMAGE: self._img_collection,
            FileType.VIDEO: self._video_collection,
        }

    def add_document_vectors(
        self,
        metadata: IndexedFileMetadata,
        chunks: list[dict[str, Any]],
    ) -> None:
        """添加文档向量。

        Args:
            metadata: 文件级元信息，随每条向量一起落盘
            chunks: 文档块列表，每个元素包含：
                - embedding: 向量 (list[float])
                - page_number: 页码 (int)
                - line_number: 行号 (int)
                - text: 块内容 (str)
                - chunk_index: 全文档单调递增的块序号 (int)

        `chunk_index` 必须落盘：检索时靠它判断两条命中是否前后相邻，从而把连续片段
        合并成一段。只有页/行号判不出来——同一页里的两块页号相同，跨页的相邻块页号又
        不连续。缺这个键的旧数据不会被合并（见 `_merge_adjacent`），不会报错。
        """
        if not chunks:
            return

        self._replace_file_vectors(self._doc_collection, metadata.path)

        base = _base_metadata(metadata)
        ids = [f"{metadata.file_id}:chunk:{i}" for i in range(len(chunks))]
        embeddings = [chunk["embedding"] for chunk in chunks]
        metadatas = [
            base
            | {
                "page_number": chunk["page_number"],
                "line_number": chunk["line_number"],
                "text": str(chunk["text"])[:_TEXT_LIMIT],
                # 落盘时兜一个默认值：processor 一直在传，但假实现/旧调用方可能没有。
                "chunk_index": int(chunk.get("chunk_index", index)),
            }
            for index, chunk in enumerate(chunks)
        ]

        self._doc_collection.add(ids=ids, embeddings=embeddings, metadatas=metadatas)

    def add_image_vectors(
        self,
        metadata: IndexedFileMetadata,
        features: list[dict[str, Any]],
    ) -> None:
        """添加图片向量。

        Args:
            metadata: 文件级元信息，随每条向量一起落盘
            features: 特征列表，每个元素包含：
                - embedding: 向量 (list[float])
                - feature_type: "ocr" | "visual"
                - text: OCR 文本（仅 ocr 类型）
        """
        if not features:
            return

        self._replace_file_vectors(self._img_collection, metadata.path)

        base = _base_metadata(metadata)
        ids = [
            f"{metadata.file_id}:{feat['feature_type']}:{i}" for i, feat in enumerate(features)
        ]
        embeddings = [feat["embedding"] for feat in features]
        metadatas = [
            base
            | {
                "feature_type": feat["feature_type"],
                "text": str(feat.get("text", ""))[:_TEXT_LIMIT],
            }
            for feat in features
        ]

        self._img_collection.add(ids=ids, embeddings=embeddings, metadatas=metadatas)

    def add_video_vectors(
        self,
        metadata: IndexedFileMetadata,
        keyframes: list[dict[str, Any]],
    ) -> None:
        """添加视频向量。

        Args:
            metadata: 文件级元信息，随每条向量一起落盘
            keyframes: 关键帧列表，每个元素包含：
                - embedding: 向量 (list[float])
                - start_time: 开始时间（秒）
                - end_time: 结束时间（秒）
        """
        if not keyframes:
            return

        self._replace_file_vectors(self._video_collection, metadata.path)

        base = _base_metadata(metadata)
        ids = [f"{metadata.file_id}:frame:{i}" for i in range(len(keyframes))]
        embeddings = [kf["embedding"] for kf in keyframes]
        metadatas = [
            base
            | {
                "start_time": kf["start_time"],
                "end_time": kf["end_time"],
            }
            for kf in keyframes
        ]

        self._video_collection.add(ids=ids, embeddings=embeddings, metadatas=metadatas)

    def search(
        self,
        query_vector: list[float],
        file_types: list[FileType],
        limit: int,
        filters: VectorSearchFilters | None = None,
    ) -> list[VectorHit]:
        """按类型检索，每种类型返回至多 limit 条命中片段。

        同一文件的多条命中怎么处理取决于类型（见 `_collapse`）：

        - **文档、视频**：向量对应文件里的不同位置，各自是一个可跳转的结果，所以保留
          多条——一份 300 页的文档里三处提到查询词就是三条。其中**前后相邻**的会先合并
          成一段，否则同一段话会被拆成几个读不通顺的碎片。
        - **图片**：OCR 文本和视觉特征是同一张图的两个侧面，不是两个位置。两条都命中
          时只保留分数最高的那条，否则同一张图会在结果列表里出现两次。

        Args:
            query_vector: 查询向量
            file_types: 要搜的媒体类型
            limit: 每种媒体类型返回的结果数上限（不是文件数；相邻片段合并后算一条）
            filters: 高级筛选条件，下推到向量库执行

        Returns:
            命中列表，按类型分组、组内按得分降序。文档和视频的同一文件可出现多次
            （命中位置互不相邻时）；图片每个文件最多一条。元信息全部取自向量元数据。
        """
        hits: list[VectorHit] = []
        for file_type in file_types:
            collection = self._collections.get(file_type)
            if collection is None:
                continue
            hits.extend(self._search_one(collection, query_vector, file_type, limit, filters))
        return hits

    def _search_one(
        self,
        collection: Any,
        query_vector: list[float],
        file_type: FileType,
        limit: int,
        filters: VectorSearchFilters | None,
    ) -> list[VectorHit]:
        name_query = (filters.name_query or "").lower() if filters else ""

        # 一律超量取回：每种类型的收敛方式都会减少条数（文档/视频合并相邻片段，
        # 图片按文件取最高分那条特征），只取 limit 条的话收敛完就不足 limit 条了。
        # 名称子串筛选同样需要——Chroma 的 where 表达不了子串，只能查回来再筛，
        # 被筛掉多少事先不知道。
        results = collection.query(
            query_embeddings=[query_vector],
            n_results=limit * _OVERFETCH_FACTOR,
            where=_build_where(filters),
        )

        ids = results.get("ids") or []
        if not ids or not ids[0]:
            return []

        metadatas = results["metadatas"][0]
        distances = results["distances"][0]

        hits: list[VectorHit] = []
        for index in range(len(ids[0])):
            metadata = metadatas[index]
            if name_query and name_query not in str(metadata.get("file_name_lower", "")):
                continue
            hits.append(_to_hit(metadata, distances[index], file_type))

        # 收敛必须在截断之前：先截断的话，topk 里本来相邻的片段会被 limit 切掉一半，
        # 合出来的是残段——正文缺一块，而区间右端点却指向被切掉的位置。
        hits = _collapse(hits, file_type)

        # 收敛会改变得分（取段内/文件内最高分），所以排序也必须在它之后。
        hits.sort(key=lambda hit: hit.score, reverse=True)
        return hits[:limit]

    def delete_file_vectors(self, file_id: str) -> None:
        """删除指定文件的所有向量。

        Args:
            file_id: 文件唯一标识
        """
        # ChromaDB 的 where 过滤删除；某个 collection 中没有该文件时 delete 是安全的空操作
        for collection in self._collections.values():
            collection.delete(where={"file_id": file_id})

    @staticmethod
    def _replace_file_vectors(collection: Any, path: str) -> None:
        """写入前清掉这个路径已有的向量，使索引成为"替换"而不是"追加"。

        不这样做，重复入库同一个文件会在库里留下多份向量：`file_id` 取自索引任务的 id
        （`TaskProcessor._describe_file` 里 `file_id=task.id`），每次入库都是新任务、
        新 id，所以旧向量既不会被覆盖也没人删得掉——`delete_file_vectors` 要按
        `file_id` 删，而调用方手里只有新的那个。表现出来就是同一个文件在搜索结果里
        重复出现，而且越重新索引越多。

        按 `path` 删而不是 `file_id`：`path` 才是物理文件的身份。
        """
        if not path:
            return
        collection.delete(where={"path": path})


def _collapse(hits: list[VectorHit], file_type: FileType) -> list[VectorHit]:
    """按类型把同一文件的多条命中收敛掉。

    两种语义，取决于同一文件的多条向量之间是什么关系：

    - **文档、视频**：向量对应文件里的不同**位置**（分块、关键帧）。不同位置各自是
      一个独立的可跳转结果，所以保留多条，只把前后相邻的合并成一段。
    - **图片**：向量对应同一张图的不同**侧面**（OCR 文本、视觉特征）。一张图就是一个
      整体，没有"跳到图片的某个位置"这种操作，所以两条特征都命中时只保留分数最高的
      那条——都返回等于同一张图在结果列表里出现两次。
    """
    if file_type is FileType.IMAGE:
        return _best_per_file(hits)
    return _merge_adjacent(hits, file_type)


def _best_per_file(hits: list[VectorHit]) -> list[VectorHit]:
    """同一文件只保留得分最高的那条命中。

    用于图片：OCR 特征和视觉特征命中的是同一张图，哪条分高就用哪条的信息——
    OCR 命中时 `snippet` 是识别出的文本，视觉命中时为空，这正好反映了它靠什么匹配上。

    分组键是 `path` 而不是 `file_id`。`file_id` 取自索引任务的 id
    （`TaskProcessor._describe_file` 里 `file_id=task.id`），同一个物理文件被重复入库
    就会拿到不同的 id——按 id 分组时这些副本各成一组，同一张图仍然重复出现。`path`
    才是物理文件的身份。`path` 为空（元数据缺失）时退回 `file_id`，至少不把几个
    不相干的文件误并成一条。
    """
    best: dict[str, VectorHit] = {}
    for hit in hits:
        key = hit.path or hit.file_id
        current = best.get(key)
        if current is None or hit.score > current.score:
            best[key] = hit
    return list(best.values())


def _merge_adjacent(hits: list[VectorHit], file_type: FileType) -> list[VectorHit]:
    """把同一文件内前后相邻的命中片段合并成一段。

    一段正文被分块切开后，命中往往落在连续的几块上。分开返回等于让用户在结果列表里
    看到同一段话的三个碎片，而且每一片都读不通顺；合并成一段既省列表空间，也让摘要
    是可读的完整上下文。

    只合并同一文件内的片段，且只在片段本身有顺序关系时合并（见 `_MERGEABLE_TYPES`）。
    合并后：

    - `snippet` 按顺序拼接，去掉分块时的重叠部分
    - 位置字段（页/行号、`start_time`）取这一段的起点，`end_time` 取终点
    - `score` 取段内最高分——一段里只要有一处高度相关，整段就该排在前面
    - `chunk_index` / `chunk_end_index` 覆盖这一段占据的区间

    不可合并的类型、以及缺 `chunk_index` 的旧数据原样返回。
    """
    if file_type not in _MERGEABLE_TYPES or len(hits) < 2:
        return hits

    # 按 file_id 分组，而不是像 `_best_per_file` 那样按 path：一次索引内部的
    # chunk_index 才是连续的。同一份文档被重复入库时两份副本的序号各自从 0 开始，
    # 按 path 合到一组会把两份的片段交错着判成"相邻"，拼出错乱的正文。
    # 重复副本本身由写入侧的 `_replace_file_vectors` 清掉，不在这里处理。
    by_file: dict[str, list[VectorHit]] = {}
    for hit in hits:
        by_file.setdefault(hit.file_id, []).append(hit)

    merged: list[VectorHit] = []
    for file_hits in by_file.values():
        if len(file_hits) < 2:
            merged.extend(file_hits)
            continue
        merged.extend(_merge_one_file(file_hits, file_type))
    return merged


def _merge_one_file(hits: list[VectorHit], file_type: FileType) -> list[VectorHit]:
    """合并单个文件内的相邻片段。"""
    ordered, unmergeable = _order_for_merge(hits, file_type)
    if not ordered:
        return unmergeable

    runs: list[list[VectorHit]] = [[ordered[0]]]
    for hit in ordered[1:]:
        if _is_adjacent(runs[-1][-1], hit, file_type):
            runs[-1].append(hit)
        else:
            runs.append([hit])

    return unmergeable + [
        run[0] if len(run) == 1 else _combine(run, file_type) for run in runs
    ]


def _order_for_merge(
    hits: list[VectorHit],
    file_type: FileType,
) -> tuple[list[VectorHit], list[VectorHit]]:
    """按位置排序，并把位置字段缺失的片段挑出来。

    缺位置的片段（旧数据没写 `chunk_index`，或关键帧没有时间）无法判断相邻，
    原样返回而不是丢掉——合并是优化，不该让结果变少。
    """
    if file_type is FileType.DOCUMENT:
        mergeable = [hit for hit in hits if hit.chunk_index is not None]
        rest = [hit for hit in hits if hit.chunk_index is None]
        mergeable.sort(key=lambda hit: hit.chunk_index or 0)
        return mergeable, rest

    mergeable = [hit for hit in hits if hit.start_time is not None]
    rest = [hit for hit in hits if hit.start_time is None]
    mergeable.sort(key=lambda hit: hit.start_time or 0.0)
    return mergeable, rest


def _is_adjacent(left: VectorHit, right: VectorHit, file_type: FileType) -> bool:
    """判断 right 是否紧接在 left 之后。

    左侧可能已经是合并过的一段，所以文档比的是它的右端点 `chunk_end_index`。
    """
    if file_type is FileType.DOCUMENT:
        left_end = left.chunk_end_index if left.chunk_end_index is not None else left.chunk_index
        if left_end is None or right.chunk_index is None:
            return False
        return right.chunk_index == left_end + 1

    if left.end_time is None or right.start_time is None:
        return False
    return abs(right.start_time - left.end_time) <= _VIDEO_ADJACENCY_TOLERANCE


def _combine(run: list[VectorHit], file_type: FileType) -> VectorHit:
    """把一串相邻片段合成一条命中。"""
    first = run[0]
    last = run[-1]
    # 一段里只要有一处高度相关，整段就该排在前面，所以取最高分而不是平均分。
    best_score = max(hit.score for hit in run)

    if file_type is FileType.DOCUMENT:
        return replace(
            first,
            score=best_score,
            snippet=_join_snippets([hit.snippet for hit in run]),
            chunk_end_index=last.chunk_end_index or last.chunk_index,
        )

    return replace(
        first,
        score=best_score,
        snippet=_join_snippets([hit.snippet for hit in run]),
        # 时间轴上的一整段：起点来自第一帧，终点来自最后一帧。
        end_time=last.end_time,
    )


def _join_snippets(snippets: list[str]) -> str:
    """顺序拼接正文，去掉分块时的重叠。

    分块器给相邻块留了重叠（`DocumentParser` 的 `overlap` 参数），直接拼会让接缝处
    的一截读两遍。逐段找出"前一段的结尾"和"后一段的开头"最长的重合并去掉它。
    """
    joined = ""
    for snippet in snippets:
        if not snippet:
            continue
        if not joined:
            joined = snippet
            continue
        joined += snippet[_overlap_length(joined, snippet) :]
    return joined


def _overlap_length(left: str, right: str) -> int:
    """left 的后缀与 right 的前缀最长的重合长度。"""
    limit = min(len(left), len(right), _MAX_CHUNK_OVERLAP)
    for size in range(limit, 0, -1):
        if left.endswith(right[:size]):
            return size
    return 0


def _build_where(filters: VectorSearchFilters | None) -> dict[str, Any] | None:
    """把筛选条件译成 Chroma 的 where 表达式。

    只处理数值范围（体积、修改时间）。名称是子串匹配，Chroma 的元数据过滤没有对应算子，
    留给调用方在结果上筛。无条件时返回 None——传空 dict 会被 Chroma 当成非法过滤器。
    """
    if filters is None:
        return None

    clauses: list[dict[str, Any]] = []
    if filters.min_size is not None:
        clauses.append({"size": {"$gte": filters.min_size}})
    if filters.max_size is not None:
        clauses.append({"size": {"$lte": filters.max_size}})

    start_ts = _iso_to_ts(filters.start_date)
    if start_ts is not None:
        clauses.append({"modified_ts": {"$gte": start_ts}})
    end_ts = _iso_to_ts(filters.end_date)
    if end_ts is not None:
        clauses.append({"modified_ts": {"$lte": end_ts}})

    if not clauses:
        return None
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}


def _to_hit(metadata: dict[str, Any], distance: float, file_type: FileType) -> VectorHit:
    """把一条向量元数据转成命中。"""
    size = metadata.get("size")
    chunk_index = metadata.get("chunk_index")
    # 单片段的区间是 [chunk_index, chunk_index]；合并后右端点会被推到最后一片。
    index = int(chunk_index) if chunk_index is not None else None
    return VectorHit(
        file_id=str(metadata["file_id"]),
        file_name=str(metadata.get("file_name", "")),
        file_type=file_type,
        score=100.0 - distance * 100,  # 距离转相似度分数
        path=str(metadata.get("path", "")),
        size=int(size) if size is not None else None,
        modified=metadata.get("modified"),
        accessible=bool(metadata.get("accessible", False)),
        snippet=str(metadata.get("text", "")),
        page_number=metadata.get("page_number"),
        line_number=metadata.get("line_number"),
        start_time=metadata.get("start_time"),
        end_time=metadata.get("end_time"),
        chunk_index=index,
        chunk_end_index=index,
    )
