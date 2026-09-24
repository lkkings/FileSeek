"""`ChromaVectorStore.search` 的检索行为。

直接对着真实的 Chroma 写入/读出，不经 `TaskProcessor`：要验的是这一层自己对
"一个文件多个命中片段"的处理，把索引侧的编排一起拉进来只会让失败原因变模糊。

同一文件的多条命中怎么收敛，取决于那些向量之间是什么关系：

- **文档、视频**：向量对应文件里不同的**位置**（分块、关键帧）。每个位置各自成为一条
  结果——一份 300 页的文档里三处提到查询词，用户要看到三个可跳转的位置。其中前后相邻
  的会合并成一段，否则同一段话被拆成几个读不通顺的碎片。
- **图片**：OCR 文本和视觉特征是同一张图的两个**侧面**，不是两个位置。两条都命中时只
  留分数最高的那条，否则同一张图会在结果列表里出现两次。

`limit` 数的是收敛之后的条数，不是文件数也不是原始向量数。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fileseek.features.tasks.domain.ports import (
    IndexedFileMetadata,
    VectorSearchFilters,
)
from fileseek.features.tasks.infrastructure.vector_store.chroma_store import (
    ChromaVectorStore,
)
from fileseek.shared.domain.file_types import FileType

# 互相正交的概念向量，Chroma 默认 squared L2：同概念距离 0，异概念距离 2.0。
# 于是分数（score = 100 - distance * 100）可以直接断言。
_CAT = [1.0, 0.0, 0.0, 0.0]
_DOG = [0.0, 1.0, 0.0, 0.0]
_UNRELATED = [0.0, 0.0, 1.0, 0.0]

EXACT_SCORE = 100.0


@pytest.fixture
def store(tmp_path: Path) -> ChromaVectorStore:
    return ChromaVectorStore(tmp_path / "vectors")


def _meta(
    file_id: str = "doc-1",
    file_name: str = "报告.pdf",
    size: int | None = 2048,
) -> IndexedFileMetadata:
    return IndexedFileMetadata(
        file_id=file_id,
        file_name=file_name,
        path=f"/library/{file_name}",
        size=size,
        modified="2026-01-01T00:00:00+00:00",
        modified_ts=1767225600.0,
        accessible=True,
    )


def _chunk(
    embedding: list[float],
    page: int,
    line: int,
    text: str,
    chunk_index: int = 0,
) -> dict[str, object]:
    """造一个文档分块。

    `chunk_index` 决定片段在全文里的位置，也就决定了哪些片段算相邻——连号的会被
    合并成一段。要验"不相邻"就把序号拉开（见 `_scattered`）。
    """
    return {
        "embedding": embedding,
        "page_number": page,
        "line_number": line,
        "text": text,
        "chunk_index": chunk_index,
    }


def _scattered(*chunks: dict[str, object]) -> list[dict[str, object]]:
    """把若干分块的 chunk_index 拉开，保证互不相邻。

    默认间隔 10，远大于"连号"所需的 1，所以它们不会被合并——用于验证
    "多个不相邻命中 → 多条结果"。
    """
    return [chunk | {"chunk_index": index * 10} for index, chunk in enumerate(chunks)]


def _consecutive(*chunks: dict[str, object]) -> list[dict[str, object]]:
    """把若干分块的 chunk_index 连号，保证前后相邻（会被合并成一段）。"""
    return [chunk | {"chunk_index": index} for index, chunk in enumerate(chunks)]


class TestMultipleSegmentsPerFile:
    """一个文件多个命中片段 → 多条结果。"""

    def test_every_matching_chunk_of_one_file_becomes_its_own_result(
        self, store: ChromaVectorStore
    ) -> None:
        """三处互不相邻的命中就是三条结果，各自带自己的页/行号。"""
        store.add_document_vectors(
            _meta(),
            _scattered(
                _chunk(_CAT, page=3, line=15, text="猫的习性"),
                _chunk(_CAT, page=42, line=7, text="猫的食谱"),
                _chunk(_CAT, page=88, line=2, text="猫的病症"),
            ),
        )

        hits = store.search(_CAT, [FileType.DOCUMENT], limit=20)

        assert len(hits) == 3
        # 全部来自同一个文件，这正是要的结果。
        assert {hit.file_id for hit in hits} == {"doc-1"}
        # 每条保留自己的命中位置，而不是共享得分最高那条的位置。
        assert {(hit.page_number, hit.line_number) for hit in hits} == {
            (3, 15),
            (42, 7),
            (88, 2),
        }
        assert {hit.snippet for hit in hits} == {"猫的习性", "猫的食谱", "猫的病症"}

    def test_non_matching_chunks_of_the_same_file_score_lower(
        self, store: ChromaVectorStore
    ) -> None:
        """不相关的分块仍会返回，但排在后面——排序按片段得分，不按文件。"""
        store.add_document_vectors(
            _meta(),
            _scattered(
                _chunk(_UNRELATED, page=1, line=1, text="无关的开场白"),
                _chunk(_CAT, page=9, line=3, text="猫的习性"),
            ),
        )

        hits = store.search(_CAT, [FileType.DOCUMENT], limit=20)

        assert [hit.page_number for hit in hits] == [9, 1]
        assert hits[0].score == EXACT_SCORE
        assert hits[0].score > hits[1].score

    def test_segments_from_several_files_interleave_by_score(
        self, store: ChromaVectorStore
    ) -> None:
        """跨文件排序也按片段得分，不先按文件分组。"""
        store.add_document_vectors(
            _meta(file_id="doc-1", file_name="甲.pdf"),
            _scattered(
                _chunk(_CAT, page=1, line=1, text="猫 A"),
                _chunk(_UNRELATED, page=2, line=1, text="无关 A"),
            ),
        )
        store.add_document_vectors(
            _meta(file_id="doc-2", file_name="乙.pdf"),
            [_chunk(_CAT, page=1, line=1, text="猫 B")],
        )

        hits = store.search(_CAT, [FileType.DOCUMENT], limit=20)

        assert len(hits) == 3
        # 两个精确命中在前（各自来自不同文件），无关的那条垫底。
        assert {hit.file_id for hit in hits[:2]} == {"doc-1", "doc-2"}
        assert all(hit.score == EXACT_SCORE for hit in hits[:2])
        assert hits[2].snippet == "无关 A"

    def test_video_keyframes_keep_their_own_clip_times(
        self, store: ChromaVectorStore
    ) -> None:
        """视频多个关键帧命中 → 多个可起播的时间段。"""
        store.add_video_vectors(
            _meta(file_id="vid-1", file_name="骑行.mp4"),
            [
                {"embedding": _CAT, "start_time": 12.0, "end_time": 30.0},
                {"embedding": _CAT, "start_time": 83.5, "end_time": 120.0},
            ],
        )

        hits = store.search(_CAT, [FileType.VIDEO], limit=20)

        assert len(hits) == 2
        assert {(hit.start_time, hit.end_time) for hit in hits} == {
            (12.0, 30.0),
            (83.5, 120.0),
        }

    def test_each_matching_image_yields_one_result(
        self, store: ChromaVectorStore
    ) -> None:
        """多张图命中 → 每张一条。图片内部的多特征收敛见 TestImagesCollapseToBestFeature。"""
        for index in (1, 2):
            store.add_image_vectors(
                _meta(file_id=f"img-{index}", file_name=f"窗台{index}.jpg"),
                [{"embedding": _CAT, "feature_type": "ocr", "text": "窗台上的猫"}],
            )

        hits = store.search(_CAT, [FileType.IMAGE], limit=20)

        assert len(hits) == 2
        assert {hit.file_id for hit in hits} == {"img-1", "img-2"}


class TestLimitCountsSegments:
    """limit 是片段数上限。"""

    def test_limit_caps_segments_not_files(self, store: ChromaVectorStore) -> None:
        """一个文件的 5 个互不相邻的命中片段，limit=2 就返回 2 条。"""
        store.add_document_vectors(
            _meta(),
            _scattered(
                *[_chunk(_CAT, page=page, line=1, text=f"猫 {page}") for page in range(1, 6)]
            ),
        )

        hits = store.search(_CAT, [FileType.DOCUMENT], limit=2)

        assert len(hits) == 2
        assert all(hit.score == EXACT_SCORE for hit in hits)

    def test_limit_applies_per_file_type(self, store: ChromaVectorStore) -> None:
        """每种类型各自算 limit，不是合计。"""
        store.add_document_vectors(
            _meta(file_id="doc-1"),
            _scattered(
                *[_chunk(_CAT, page=page, line=1, text=f"猫 {page}") for page in range(1, 4)]
            ),
        )
        store.add_video_vectors(
            _meta(file_id="vid-1", file_name="a.mp4"),
            # 时间段之间留空档，否则首尾相接的关键帧会被合并成一段。
            [
                {"embedding": _CAT, "start_time": float(i * 10), "end_time": float(i * 10 + 1)}
                for i in range(3)
            ],
        )

        hits = store.search(_CAT, [FileType.DOCUMENT, FileType.VIDEO], limit=2)

        assert len(hits) == 4
        assert sum(hit.file_type is FileType.DOCUMENT for hit in hits) == 2
        assert sum(hit.file_type is FileType.VIDEO for hit in hits) == 2


class TestFiltersStillApply:
    """改动收敛方式之后，筛选仍要正常工作。"""

    def test_name_filter_keeps_every_segment_of_the_matching_file(
        self, store: ChromaVectorStore
    ) -> None:
        """名称子串筛掉整个文件，留下的文件保留全部命中片段。"""
        store.add_document_vectors(
            _meta(file_id="doc-1", file_name="季度报告.pdf"),
            _scattered(
                _chunk(_CAT, page=1, line=1, text="猫 A"),
                _chunk(_CAT, page=2, line=1, text="猫 B"),
            ),
        )
        store.add_document_vectors(
            _meta(file_id="doc-2", file_name="年度总结.pdf"),
            [_chunk(_CAT, page=1, line=1, text="猫 C")],
        )

        hits = store.search(
            _CAT,
            [FileType.DOCUMENT],
            limit=20,
            filters=VectorSearchFilters(name_query="季度"),
        )

        assert len(hits) == 2
        assert {hit.file_id for hit in hits} == {"doc-1"}

    def test_name_filter_is_case_insensitive(self, store: ChromaVectorStore) -> None:
        store.add_document_vectors(
            _meta(file_id="doc-1", file_name="Report.PDF"),
            [_chunk(_CAT, page=1, line=1, text="猫")],
        )

        hits = store.search(
            _CAT,
            [FileType.DOCUMENT],
            limit=20,
            filters=VectorSearchFilters(name_query="report"),
        )

        assert len(hits) == 1

    def test_size_filter_excludes_the_whole_file(self, store: ChromaVectorStore) -> None:
        store.add_document_vectors(
            _meta(file_id="small", file_name="小.pdf", size=100),
            [_chunk(_CAT, page=1, line=1, text="猫")],
        )
        store.add_document_vectors(
            _meta(file_id="big", file_name="大.pdf", size=10_000),
            [_chunk(_CAT, page=1, line=1, text="猫")],
        )

        hits = store.search(
            _CAT,
            [FileType.DOCUMENT],
            limit=20,
            filters=VectorSearchFilters(min_size=1000),
        )

        assert [hit.file_id for hit in hits] == ["big"]


class TestEmptyResults:
    def test_no_vectors_yields_no_hits(self, store: ChromaVectorStore) -> None:
        assert store.search(_CAT, [FileType.DOCUMENT], limit=20) == []

    def test_deleting_a_file_removes_all_of_its_segments(
        self, store: ChromaVectorStore
    ) -> None:
        store.add_document_vectors(
            _meta(),
            _scattered(
                _chunk(_CAT, page=1, line=1, text="猫 A"),
                _chunk(_CAT, page=2, line=1, text="猫 B"),
            ),
        )
        assert len(store.search(_CAT, [FileType.DOCUMENT], limit=20)) == 2

        store.delete_file_vectors("doc-1")

        assert store.search(_CAT, [FileType.DOCUMENT], limit=20) == []

    def test_unsearched_type_is_skipped(self, store: ChromaVectorStore) -> None:
        store.add_document_vectors(_meta(), [_chunk(_CAT, page=1, line=1, text="猫")])

        assert store.search(_CAT, [FileType.IMAGE], limit=20) == []


class TestMergeAdjacentDocumentChunks:
    """连号的文档片段合并成一段。"""

    def test_consecutive_chunks_become_one_segment(
        self, store: ChromaVectorStore
    ) -> None:
        """三个连号片段 → 一条结果，正文按顺序拼接。"""
        store.add_document_vectors(
            _meta(),
            _consecutive(
                _chunk(_CAT, page=3, line=1, text="猫是一种"),
                _chunk(_CAT, page=3, line=4, text="独居的"),
                _chunk(_CAT, page=3, line=7, text="捕食动物"),
            ),
        )

        hits = store.search(_CAT, [FileType.DOCUMENT], limit=20)

        assert len(hits) == 1
        assert hits[0].snippet == "猫是一种独居的捕食动物"
        # 位置取这一段的起点，区间覆盖全部三片。
        assert hits[0].page_number == 3
        assert hits[0].line_number == 1
        assert hits[0].chunk_index == 0
        assert hits[0].chunk_end_index == 2

    def test_non_consecutive_chunks_stay_separate(
        self, store: ChromaVectorStore
    ) -> None:
        """序号不连号就不合并——它们在原文里本来隔着别的内容。"""
        store.add_document_vectors(
            _meta(),
            [
                _chunk(_CAT, page=1, line=1, text="前段", chunk_index=0),
                _chunk(_CAT, page=50, line=1, text="后段", chunk_index=40),
            ],
        )

        hits = store.search(_CAT, [FileType.DOCUMENT], limit=20)

        assert len(hits) == 2
        assert {hit.snippet for hit in hits} == {"前段", "后段"}

    def test_two_runs_in_one_file_merge_independently(
        self, store: ChromaVectorStore
    ) -> None:
        """一个文件里两段各自连续的命中 → 两条结果，各自合并。"""
        store.add_document_vectors(
            _meta(),
            [
                _chunk(_CAT, page=1, line=1, text="第一段A", chunk_index=0),
                _chunk(_CAT, page=1, line=5, text="第一段B", chunk_index=1),
                _chunk(_CAT, page=9, line=1, text="第二段A", chunk_index=30),
                _chunk(_CAT, page=9, line=5, text="第二段B", chunk_index=31),
            ],
        )

        hits = store.search(_CAT, [FileType.DOCUMENT], limit=20)

        assert len(hits) == 2
        assert {hit.snippet for hit in hits} == {"第一段A第一段B", "第二段A第二段B"}
        assert {(hit.chunk_index, hit.chunk_end_index) for hit in hits} == {(0, 1), (30, 31)}

    def test_merged_segment_takes_the_best_score_in_the_run(
        self, store: ChromaVectorStore
    ) -> None:
        """段内一处高度相关，整段就按那个分数排序。

        否则一段话里最相关的那句会被周围不相关的句子拉低平均分，
        把整段挤出 topk。
        """
        store.add_document_vectors(
            _meta(file_id="doc-merged"),
            _consecutive(
                _chunk(_UNRELATED, page=1, line=1, text="无关的前言"),
                _chunk(_CAT, page=1, line=5, text="猫的习性"),
            ),
        )
        # 另一个文件只有一条中等相关的命中，用来确认合并段确实排在它前面。
        store.add_document_vectors(
            _meta(file_id="doc-single", file_name="别的.pdf"),
            [_chunk(_UNRELATED, page=1, line=1, text="也无关")],
        )

        hits = store.search(_CAT, [FileType.DOCUMENT], limit=20)

        merged = next(hit for hit in hits if hit.file_id == "doc-merged")
        assert merged.score == EXACT_SCORE
        # 合并段排在前面。
        assert hits[0].file_id == "doc-merged"

    def test_merge_does_not_cross_file_boundaries(
        self, store: ChromaVectorStore
    ) -> None:
        """两个文件的片段序号即使连号也不能合并。"""
        store.add_document_vectors(
            _meta(file_id="doc-1", file_name="甲.pdf"),
            [_chunk(_CAT, page=1, line=1, text="甲的内容", chunk_index=0)],
        )
        store.add_document_vectors(
            _meta(file_id="doc-2", file_name="乙.pdf"),
            [_chunk(_CAT, page=1, line=1, text="乙的内容", chunk_index=1)],
        )

        hits = store.search(_CAT, [FileType.DOCUMENT], limit=20)

        assert len(hits) == 2
        assert {hit.snippet for hit in hits} == {"甲的内容", "乙的内容"}

    def test_overlapping_text_is_not_duplicated_when_joined(
        self, store: ChromaVectorStore
    ) -> None:
        """分块留的重叠在拼接时去掉，否则接缝处会读两遍。"""
        store.add_document_vectors(
            _meta(),
            _consecutive(
                _chunk(_CAT, page=1, line=1, text="猫是一种独居的捕食动物"),
                # 前一块的尾巴"捕食动物"是分块 overlap 带来的重复。
                _chunk(_CAT, page=1, line=3, text="捕食动物，夜间活动"),
            ),
        )

        hits = store.search(_CAT, [FileType.DOCUMENT], limit=20)

        assert len(hits) == 1
        assert hits[0].snippet == "猫是一种独居的捕食动物，夜间活动"

    def test_chunks_without_index_are_not_merged_but_still_returned(
        self, store: ChromaVectorStore
    ) -> None:
        """缺 chunk_index 的旧数据不参与合并，但不能因此丢掉。

        合并是优化，老索引没有这个键时应当退化成"各自一条"，而不是报错或少结果。
        """
        base = _meta()
        # 绕过 add_document_vectors 的默认值补全，直接写不含 chunk_index 的元数据，
        # 模拟这个键落盘之前建立的索引。
        store._doc_collection.add(  # noqa: SLF001 - 就是要造老格式的数据
            ids=["doc-1:chunk:0", "doc-1:chunk:1"],
            embeddings=[_CAT, _CAT],
            metadatas=[
                {
                    "file_id": base.file_id,
                    "file_name": base.file_name,
                    "file_name_lower": base.file_name.lower(),
                    "path": base.path,
                    "accessible": True,
                    "text": "老数据A",
                },
                {
                    "file_id": base.file_id,
                    "file_name": base.file_name,
                    "file_name_lower": base.file_name.lower(),
                    "path": base.path,
                    "accessible": True,
                    "text": "老数据B",
                },
            ],
        )

        hits = store.search(_CAT, [FileType.DOCUMENT], limit=20)

        assert len(hits) == 2
        assert {hit.snippet for hit in hits} == {"老数据A", "老数据B"}


class TestMergeAdjacentVideoKeyframes:
    """时间轴上首尾相接的关键帧合并成一段。"""

    def test_contiguous_keyframes_become_one_clip(
        self, store: ChromaVectorStore
    ) -> None:
        """三个相接的关键帧 → 一个时间段，起止时间覆盖全程。"""
        store.add_video_vectors(
            _meta(file_id="vid-1", file_name="骑行.mp4"),
            [
                {"embedding": _CAT, "start_time": 10.0, "end_time": 12.0},
                {"embedding": _CAT, "start_time": 12.0, "end_time": 14.0},
                {"embedding": _CAT, "start_time": 14.0, "end_time": 16.0},
            ],
        )

        hits = store.search(_CAT, [FileType.VIDEO], limit=20)

        assert len(hits) == 1
        assert (hits[0].start_time, hits[0].end_time) == (10.0, 16.0)

    def test_keyframes_with_a_gap_stay_separate(
        self, store: ChromaVectorStore
    ) -> None:
        """中间断开的关键帧是两个独立片段，前端要给两个起播点。"""
        store.add_video_vectors(
            _meta(file_id="vid-1", file_name="骑行.mp4"),
            [
                {"embedding": _CAT, "start_time": 10.0, "end_time": 12.0},
                {"embedding": _CAT, "start_time": 90.0, "end_time": 92.0},
            ],
        )

        hits = store.search(_CAT, [FileType.VIDEO], limit=20)

        assert len(hits) == 2
        assert {(hit.start_time, hit.end_time) for hit in hits} == {
            (10.0, 12.0),
            (90.0, 92.0),
        }

    def test_float_jitter_still_counts_as_contiguous(
        self, store: ChromaVectorStore
    ) -> None:
        """采样出的时间是浮点，差着极小的量也该算相接。"""
        store.add_video_vectors(
            _meta(file_id="vid-1", file_name="骑行.mp4"),
            [
                {"embedding": _CAT, "start_time": 10.0, "end_time": 12.0},
                {"embedding": _CAT, "start_time": 12.0000004, "end_time": 14.0},
            ],
        )

        hits = store.search(_CAT, [FileType.VIDEO], limit=20)

        assert len(hits) == 1
        assert (hits[0].start_time, hits[0].end_time) == (10.0, 14.0)


class TestImagesCollapseToBestFeature:
    """一张图两条特征都命中时只留分数最高的那条。

    OCR 文本和视觉特征是同一张图的两个侧面，不是图里的两个位置——没有"跳到图片的
    某一处"这种操作。两条都返回等于同一张图在结果列表里出现两次。
    """

    def test_both_features_matching_yields_one_result(
        self, store: ChromaVectorStore
    ) -> None:
        store.add_image_vectors(
            _meta(file_id="img-1", file_name="窗台.jpg"),
            [
                {"embedding": _CAT, "feature_type": "ocr", "text": "窗台上的猫"},
                {"embedding": _CAT, "feature_type": "visual"},
            ],
        )

        hits = store.search(_CAT, [FileType.IMAGE], limit=20)

        assert len(hits) == 1
        assert hits[0].file_id == "img-1"

    def test_the_higher_scoring_feature_wins(self, store: ChromaVectorStore) -> None:
        """视觉特征分更高时用它，`snippet` 因此是空的——它不是靠文字匹配上的。"""
        store.add_image_vectors(
            _meta(file_id="img-1", file_name="窗台.jpg"),
            [
                # OCR 文本与查询无关，视觉特征精确命中。
                {"embedding": _UNRELATED, "feature_type": "ocr", "text": "一段无关文字"},
                {"embedding": _CAT, "feature_type": "visual"},
            ],
        )

        hits = store.search(_CAT, [FileType.IMAGE], limit=20)

        assert len(hits) == 1
        assert hits[0].score == EXACT_SCORE
        assert hits[0].snippet == ""

    def test_ocr_wins_when_it_scores_higher(self, store: ChromaVectorStore) -> None:
        """反过来 OCR 分更高时，`snippet` 带回识别出的文本供前端展示。"""
        store.add_image_vectors(
            _meta(file_id="img-1", file_name="窗台.jpg"),
            [
                {"embedding": _CAT, "feature_type": "ocr", "text": "窗台上的猫"},
                {"embedding": _UNRELATED, "feature_type": "visual"},
            ],
        )

        hits = store.search(_CAT, [FileType.IMAGE], limit=20)

        assert len(hits) == 1
        assert hits[0].score == EXACT_SCORE
        assert hits[0].snippet == "窗台上的猫"

    def test_several_images_each_keep_their_best_feature(
        self, store: ChromaVectorStore
    ) -> None:
        """收敛是按文件各自进行的，不会把不同图片也合掉。"""
        store.add_image_vectors(
            _meta(file_id="img-1", file_name="甲.jpg"),
            [
                {"embedding": _CAT, "feature_type": "ocr", "text": "甲里的猫"},
                {"embedding": _UNRELATED, "feature_type": "visual"},
            ],
        )
        store.add_image_vectors(
            _meta(file_id="img-2", file_name="乙.jpg"),
            [
                {"embedding": _UNRELATED, "feature_type": "ocr", "text": "乙的无关文字"},
                {"embedding": _CAT, "feature_type": "visual"},
            ],
        )

        hits = store.search(_CAT, [FileType.IMAGE], limit=20)

        assert len(hits) == 2
        assert {hit.file_id for hit in hits} == {"img-1", "img-2"}
        # 两张图各自留下的都是精确命中的那条特征。
        assert all(hit.score == EXACT_SCORE for hit in hits)

    def test_reindexing_the_same_image_does_not_duplicate_it(
        self, store: ChromaVectorStore
    ) -> None:
        """同一张图重复入库后仍然只有一条结果。

        `file_id` 取自索引任务的 id，重复入库会拿到一个新 id，所以按 `file_id` 分组
        收敛不掉这些副本——同一张图会在结果里出现多次，越重新索引越多。写入侧按 `path`
        先清旧向量，检索侧也按 `path` 分组，两道都要有。
        """
        features = [
            {"embedding": _CAT, "feature_type": "ocr", "text": "窗台上的猫"},
            {"embedding": _CAT, "feature_type": "visual"},
        ]
        # 两次入库同一个路径，但 file_id 不同——模拟重新索引。
        store.add_image_vectors(_meta(file_id="task-1", file_name="窗台.jpg"), features)
        store.add_image_vectors(_meta(file_id="task-2", file_name="窗台.jpg"), features)

        hits = store.search(_CAT, [FileType.IMAGE], limit=20)

        assert len(hits) == 1
        # 留下的是最新那次索引的向量。
        assert hits[0].file_id == "task-2"

    def test_preexisting_duplicates_still_collapse_on_read(
        self, store: ChromaVectorStore
    ) -> None:
        """库里已有的重复副本在检索时也要收敛掉。

        写入侧的清理只能防止**新**产生重复；这个键落地之前建立的索引里已经躺着多份
        副本。检索侧按 `path` 分组是治这些存量数据的那道防线，所以这里绕过写入路径
        直接造出重复，验证读的时候仍然只返回一条。
        """
        base = _meta(file_id="old-task", file_name="窗台.jpg")
        shared = {
            "file_name": base.file_name,
            "file_name_lower": base.file_name.lower(),
            "path": base.path,
            "accessible": True,
        }
        # 直接写 collection，绕开 add_image_vectors 的按 path 清理。
        store._img_collection.add(  # noqa: SLF001 - 就是要造出存量重复数据
            ids=["old-task:ocr:0", "new-task:ocr:0", "new-task:visual:1"],
            embeddings=[_CAT, _CAT, _CAT],
            metadatas=[
                shared | {"file_id": "old-task", "feature_type": "ocr", "text": "猫"},
                shared | {"file_id": "new-task", "feature_type": "ocr", "text": "猫"},
                shared | {"file_id": "new-task", "feature_type": "visual", "text": ""},
            ],
        )

        hits = store.search(_CAT, [FileType.IMAGE], limit=20)

        # 三条向量、两个 file_id，但只是一张图。
        assert len(hits) == 1
        assert hits[0].path == base.path

    def test_reindexing_does_not_duplicate_documents_either(
        self, store: ChromaVectorStore
    ) -> None:
        """重复入库的问题不限于图片，文档同样不该翻倍。"""
        chunks = _scattered(
            _chunk(_CAT, page=1, line=1, text="猫 A"),
            _chunk(_CAT, page=9, line=1, text="猫 B"),
        )
        store.add_document_vectors(_meta(file_id="task-1"), chunks)
        store.add_document_vectors(_meta(file_id="task-2"), chunks)

        hits = store.search(_CAT, [FileType.DOCUMENT], limit=20)

        # 两个互不相邻的片段，各一条——而不是两次索引叠成四条。
        assert len(hits) == 2
        assert {hit.file_id for hit in hits} == {"task-2"}

    def test_limit_counts_collapsed_images(self, store: ChromaVectorStore) -> None:
        """limit 数的是收敛后的条数：3 张图各 2 条特征，limit=2 返回 2 条。"""
        for index in range(1, 4):
            store.add_image_vectors(
                _meta(file_id=f"img-{index}", file_name=f"图{index}.jpg"),
                [
                    {"embedding": _CAT, "feature_type": "ocr", "text": f"猫 {index}"},
                    {"embedding": _CAT, "feature_type": "visual"},
                ],
            )

        hits = store.search(_CAT, [FileType.IMAGE], limit=2)

        assert len(hits) == 2
        # 两条来自不同文件，而不是同一张图的两条特征。
        assert len({hit.file_id for hit in hits}) == 2
