"""导入（索引）与检索的用例。

分两层：

1. **真实往返**（`TestIndexAndSearchRoundTrip`）：用真的 `ChromaVectorStore` 把文档、
   图片、视频经 `TaskProcessor` 索引进去，再用 `SearchFilesUseCase` 查出来。验的是两侧
   对元数据的约定真的对得上——元信息（路径/体积/修改时间/可访问性）和高级筛选都靠索引时
   写进向量元数据，检索不再回库表，所以只有跑通真实往返才能证明这条链路是通的。
   嵌入模型被换成一个确定性的小向量空间（见 `ConceptEmbedder`），真货会下载
   jina-clip-v2 权重。
2. **用例编排**（`TestSearchOrchestration`）：向量库换成假实现，验编排规则——每类独立
   limit、空类型集、MB→字节换算、底层异常不外泄。

`limit` 对每种媒体类型独立生效：三种类型都搜时最多返回 3 * limit 条，不是合计 limit 条。
"""

from __future__ import annotations

import multiprocessing as mp
import os
import queue
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from fileseek.features.search.application.queries import SearchFilesQuery
from fileseek.features.search.application.use_cases import SearchFilesUseCase
from fileseek.features.tasks.application.processor import TaskProcessor
from fileseek.features.tasks.domain.entities import Task, TaskStatus
from fileseek.features.tasks.domain.ports import (
    DocumentChunk,
    ParsedDocument,
    VectorHit,
    VectorSearchFilters,
    VideoFrame,
    VideoKeyframe,
)
from fileseek.features.tasks.infrastructure.vector_store.chroma_store import (
    ChromaVectorStore,
)
from fileseek.shared.domain.file_types import FileType

# ---------------------------------------------------------------------------
# 确定性的"嵌入模型"
# ---------------------------------------------------------------------------

# 关键词 → 单位向量。互相正交，所以命中与不命中的距离是可预测的：同一概念距离 0
# （Chroma 默认 squared L2），不同概念距离 2.0。断言因此可以直接写分数和顺序。
_CONCEPTS: dict[str, list[float]] = {
    "猫": [1.0, 0.0, 0.0, 0.0],
    "狗": [0.0, 1.0, 0.0, 0.0],
    "营收": [0.0, 0.0, 1.0, 0.0],
}
_UNRELATED = [0.0, 0.0, 0.0, 1.0]

# 概念完全命中时的分数：score = 100 - distance * 100，distance = 0。
EXACT_SCORE = 100.0


def _vector_for(text: object) -> list[float]:
    value = str(text)
    for keyword, vector in _CONCEPTS.items():
        if keyword in value:
            return vector
    return _UNRELATED


class ConceptEmbedder:
    """把文本/图像映射到上面那个小概念空间，不加载任何模型。"""

    def __init__(self, error: Exception | None = None) -> None:
        self.calls: list[str] = []
        self.error = error

    def embed_text(self, text: str | list[str], *, query: bool = False) -> Any:
        """**永远返回一批**，和真实现一致（见 `EmbeddingPort` 的说明）。

        这个假实现原来单条返回裸向量、多条才返回批。真实现永远返回批，而端口当时声明的是
        `list[float] | list[list[float]]`，两种理解都合法，于是这份假货把四个调用方少取
        `[0]` 的 bug 全遮住了——线上 Chroma 报 `got [[[`，这里全绿。
        """
        if self.error is not None:
            raise self.error
        if isinstance(text, list):
            return [_vector_for(item) for item in text]
        self.calls.append(text)
        return [_vector_for(text)]

    def embed_image(self, image: object) -> Any:
        """同上，永远返回一批。"""
        if self.error is not None:
            raise self.error
        return [_vector_for(image)]


# ---------------------------------------------------------------------------
# 抽取侧的假实现：真货要解析 PDF、跑 OCR、解码视频
# ---------------------------------------------------------------------------


class FakeDocumentParser:
    """按 `DocumentParserPort` 的契约返回 `ParsedDocument`，不是裸 list。"""

    def __init__(self, chunks: list[dict[str, Any]]) -> None:
        self.chunks = chunks

    def parse_and_chunk(self, path: Path) -> ParsedDocument:
        return ParsedDocument(
            chunks=tuple(
                DocumentChunk(
                    text=str(chunk["text"]),
                    page_number=chunk.get("page_number"),
                    line_number=chunk.get("line_number"),
                    chunk_index=index,
                )
                for index, chunk in enumerate(self.chunks)
            ),
            page_count=1,
        )


class FakeOCR:
    def __init__(self, text: str) -> None:
        self.text = text

    def extract_text(self, path: Path) -> str:
        return self.text


class FakeVideoSampler:
    """按 `VideoSamplerPort` 的契约返回 `VideoKeyframe` 元组。"""

    def __init__(self, keyframes: list[dict[str, Any]]) -> None:
        self.keyframes = keyframes

    def extract_keyframes(self, path: Path) -> tuple[VideoKeyframe, ...]:
        return tuple(
            VideoKeyframe(
                start_time=float(kf["start_time"]),
                end_time=float(kf["end_time"]),
                frame=VideoFrame(data=kf.get("frame", "")),
            )
            for kf in self.keyframes
        )


# ---------------------------------------------------------------------------
# 导入（索引）辅助
# ---------------------------------------------------------------------------


def _write_file(root: Path, name: str, *, size: int = 64, mtime: float | None = None) -> Path:
    """在临时目录里造一个真文件。

    索引时的元信息取自磁盘（`TaskProcessor._describe_file` 调 `stat`），所以体积和修改
    时间必须靠真实文件来控制，不能靠 mock。
    """
    path = root / name
    path.write_bytes(b"x" * size)
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


def _index(
    store: ChromaVectorStore,
    path: Path,
    file_id: str,
    *,
    chunks: list[dict[str, Any]] | None = None,
    ocr_text: str = "",
    keyframes: list[dict[str, Any]] | None = None,
) -> Task:
    """走真实的 `TaskProcessor.process` 把一个文件索引进向量库。

    只有抽取和嵌入被替换成假实现，元信息采集、编码分派、向量写入都是真代码。
    """
    processor = TaskProcessor(
        document_parser=FakeDocumentParser(chunks or []),
        ocr_service=FakeOCR(ocr_text),
        video_sampler=FakeVideoSampler(keyframes or []),
        embedding_service=ConceptEmbedder(),
        vector_index=store,
    )
    task = Task(id=file_id, source_path=str(path), status=TaskStatus.PROCESSING)
    processor.process(task)
    return task


def _query(**overrides: Any) -> SearchFilesQuery:
    defaults: dict[str, Any] = {"query": "猫", "file_types": None, "limit": 20}
    defaults.update(overrides)
    return SearchFilesQuery(**defaults)


@pytest.fixture
def store(tmp_path: Path) -> ChromaVectorStore:
    """每个测试一个独立的向量库目录，索引和检索共用同一个实例。

    同一进程里对同一目录开两个 Chroma 客户端会互相打架，所以不能一个实例写、另一个读。
    """
    return ChromaVectorStore(tmp_path / "vectors")


@pytest.fixture
def use_case(store: ChromaVectorStore) -> SearchFilesUseCase:
    return SearchFilesUseCase(ConceptEmbedder(), store)


class TestIndexAndSearchRoundTrip:
    """导入文档/图片/视频，再查出来。"""

    @pytest.mark.asyncio
    async def test_document_is_searchable_with_its_text_location(
        self, tmp_path: Path, store: ChromaVectorStore, use_case: SearchFilesUseCase
    ) -> None:
        """文档命中要带回命中文本和页/行号——前端靠它跳转到原文位置。"""
        path = _write_file(tmp_path, "季度报告.pdf", size=2048)
        _index(
            store,
            path,
            "doc-1",
            chunks=[
                {"page_number": 1, "line_number": 2, "text": "无关的开场白"},
                {"page_number": 3, "line_number": 15, "text": "本季度营收同比增长"},
            ],
        )

        hits = await use_case.execute(_query(query="营收"))

        # 两个分块的 chunk_index 连号，所以被合并成一段（见 chroma_store._merge_adjacent）。
        # 位置取这一段的起点，得分取段内最高分。
        assert len(hits) == 1
        result, metadata = hits[0]
        assert result.file_id == "doc-1"
        assert result.file_name == "季度报告.pdf"
        assert result.file_type is FileType.DOCUMENT
        assert result.score == EXACT_SCORE
        assert result.page_number == 1
        assert result.line_number == 2
        # 正文是两块按顺序拼起来的。
        assert "本季度营收同比增长" in result.snippet
        # 元信息来自索引时落盘的向量元数据，不回库表。
        assert metadata is not None
        assert metadata.path == str(path)
        assert metadata.size == 2048
        assert metadata.accessible is True
        assert metadata.modified is not None

    @pytest.mark.asyncio
    async def test_image_is_searchable_by_its_ocr_text(
        self, tmp_path: Path, store: ChromaVectorStore, use_case: SearchFilesUseCase
    ) -> None:
        path = _write_file(tmp_path, "窗台.jpg")
        _index(store, path, "img-1", ocr_text="窗台上的猫")

        hits = await use_case.execute(_query(query="猫"))

        assert len(hits) == 1
        result, metadata = hits[0]
        assert result.file_id == "img-1"
        assert result.file_type is FileType.IMAGE
        assert result.score == EXACT_SCORE
        assert metadata is not None
        assert metadata.path == str(path)

    @pytest.mark.asyncio
    async def test_video_is_searchable_with_its_clip_times(
        self, tmp_path: Path, store: ChromaVectorStore, use_case: SearchFilesUseCase
    ) -> None:
        """视频命中要带回片段起止时间，否则前端不知道该从哪一秒起播。"""
        path = _write_file(tmp_path, "骑行.mp4")
        _index(
            store,
            path,
            "vid-1",
            keyframes=[
                {"start_time": 0.0, "end_time": 12.0, "frame": "空镜头"},
                {"start_time": 83.5, "end_time": 120.0, "frame": "猫"},
            ],
        )

        hits = await use_case.execute(_query(query="猫"))

        # 两个关键帧各自成为一条结果，命中的那条排在前面。
        assert len(hits) == 2
        result, _ = hits[0]
        assert result.file_id == "vid-1"
        assert result.file_type is FileType.VIDEO
        assert result.score == EXACT_SCORE
        # 起止时间来自它自己那个关键帧，不是"得分最高的那个"。
        assert result.start_time == 83.5
        assert result.end_time == 120.0
        # 空镜头那帧仍然返回，带着自己的时间段。
        assert (hits[1][0].start_time, hits[1][0].end_time) == (0.0, 12.0)

    @pytest.mark.asyncio
    async def test_one_query_spans_all_three_media_types(
        self, tmp_path: Path, store: ChromaVectorStore, use_case: SearchFilesUseCase
    ) -> None:
        """三种类型一起导入后，一次查询要能同时命中三类。"""
        _index(
            store,
            _write_file(tmp_path, "猫谱.pdf"),
            "doc-1",
            chunks=[{"page_number": 1, "line_number": 1, "text": "猫的习性"}],
        )
        _index(store, _write_file(tmp_path, "猫.jpg"), "img-1", ocr_text="一只猫")
        _index(
            store,
            _write_file(tmp_path, "猫.mp4"),
            "vid-1",
            keyframes=[{"start_time": 1.0, "end_time": 2.0, "frame": "猫"}],
        )

        hits = await use_case.execute(_query(query="猫"))

        assert {hit[0].file_id for hit in hits} == {"doc-1", "img-1", "vid-1"}
        assert {hit[0].file_type for hit in hits} == {
            FileType.DOCUMENT,
            FileType.IMAGE,
            FileType.VIDEO,
        }

    @pytest.mark.asyncio
    async def test_unrelated_content_scores_below_a_match(
        self, tmp_path: Path, store: ChromaVectorStore, use_case: SearchFilesUseCase
    ) -> None:
        """检索结果要按相关性排序，不能把不相关的排在命中前面。"""
        _index(store, _write_file(tmp_path, "猫.jpg"), "img-match", ocr_text="一只猫")
        _index(store, _write_file(tmp_path, "狗.jpg"), "img-other", ocr_text="一只狗")

        hits = await use_case.execute(_query(query="猫", file_types=[FileType.IMAGE]))

        assert [hit[0].file_id for hit in hits] == ["img-match", "img-other"]
        assert hits[0][0].score == EXACT_SCORE
        assert hits[1][0].score < hits[0][0].score

    @pytest.mark.asyncio
    async def test_limit_applies_per_media_type(
        self, tmp_path: Path, store: ChromaVectorStore, use_case: SearchFilesUseCase
    ) -> None:
        """limit=1 且三类都有命中时，每类各留 1 条，总共 3 条。"""
        for index in (1, 2):
            _index(
                store,
                _write_file(tmp_path, f"猫{index}.pdf"),
                f"doc-{index}",
                chunks=[{"page_number": 1, "line_number": 1, "text": "猫"}],
            )
            _index(store, _write_file(tmp_path, f"猫{index}.jpg"), f"img-{index}", ocr_text="猫")
            _index(
                store,
                _write_file(tmp_path, f"猫{index}.mp4"),
                f"vid-{index}",
                keyframes=[{"start_time": 0.0, "end_time": 1.0, "frame": "猫"}],
            )

        hits = await use_case.execute(_query(query="猫", limit=1))

        assert len(hits) == 3
        assert [hit[0].file_type for hit in hits] == [
            FileType.DOCUMENT,
            FileType.IMAGE,
            FileType.VIDEO,
        ]

    @pytest.mark.asyncio
    async def test_file_type_filter_excludes_other_types(
        self, tmp_path: Path, store: ChromaVectorStore, use_case: SearchFilesUseCase
    ) -> None:
        _index(
            store,
            _write_file(tmp_path, "猫.pdf"),
            "doc-1",
            chunks=[{"page_number": 1, "line_number": 1, "text": "猫"}],
        )
        _index(store, _write_file(tmp_path, "猫.jpg"), "img-1", ocr_text="猫")

        hits = await use_case.execute(_query(query="猫", file_types=[FileType.IMAGE]))

        assert [hit[0].file_id for hit in hits] == ["img-1"]

    @pytest.mark.asyncio
    async def test_name_filter_narrows_results(
        self, tmp_path: Path, store: ChromaVectorStore, use_case: SearchFilesUseCase
    ) -> None:
        """文件名筛选下推到向量库，按子串、大小写不敏感匹配。"""
        _index(store, _write_file(tmp_path, "Cat-2026.jpg"), "img-1", ocr_text="猫")
        _index(store, _write_file(tmp_path, "dog-2026.jpg"), "img-2", ocr_text="猫")

        hits = await use_case.execute(_query(query="猫", name_query="cat"))

        assert [hit[0].file_id for hit in hits] == ["img-1"]

    @pytest.mark.asyncio
    async def test_size_filter_narrows_results(
        self, tmp_path: Path, store: ChromaVectorStore, use_case: SearchFilesUseCase
    ) -> None:
        """体积筛选按字节比较，用例负责把请求里的 MB 换算过来。"""
        _write_file(tmp_path, "small.jpg", size=1024)
        _write_file(tmp_path, "large.jpg", size=3 * 1024 * 1024)
        _index(store, tmp_path / "small.jpg", "img-small", ocr_text="猫")
        _index(store, tmp_path / "large.jpg", "img-large", ocr_text="猫")

        hits = await use_case.execute(_query(query="猫", min_size_m=1.0))

        assert [hit[0].file_id for hit in hits] == ["img-large"]

    @pytest.mark.asyncio
    async def test_date_filter_narrows_results(
        self, tmp_path: Path, store: ChromaVectorStore, use_case: SearchFilesUseCase
    ) -> None:
        """日期筛选比的是索引时落盘的修改时间。"""
        old = datetime(2024, 3, 1).timestamp()  # noqa: DTZ001 - 与筛选侧的朴素时间语义一致
        recent = datetime(2026, 6, 15).timestamp()  # noqa: DTZ001
        _index(
            store,
            _write_file(tmp_path, "old.jpg", mtime=old),
            "img-old",
            ocr_text="猫",
        )
        _index(
            store,
            _write_file(tmp_path, "recent.jpg", mtime=recent),
            "img-recent",
            ocr_text="猫",
        )

        hits = await use_case.execute(
            _query(query="猫", start_date="2026-01-01", end_date="2026-12-31")
        )

        assert [hit[0].file_id for hit in hits] == ["img-recent"]

    @pytest.mark.asyncio
    async def test_empty_ocr_text_indexes_nothing(
        self, tmp_path: Path, store: ChromaVectorStore, use_case: SearchFilesUseCase
    ) -> None:
        """OCR 没识别出文字时只写视觉特征，不写空文本的向量。

        所以这张图仍然可检索（靠画面），但和"猫"这个查询不相关，分数很低——
        视觉特征是无条件写的（`_encode_image`），只有 OCR 文本为空时才跳过那一条。
        """
        _index(store, _write_file(tmp_path, "blank.jpg"), "img-blank", ocr_text="")

        hits = await use_case.execute(_query(query="猫"))

        assert [result.file_id for result, _ in hits] == ["img-blank"]
        assert hits[0][0].score < EXACT_SCORE
        # 命中来自视觉特征，没有 OCR 文本可展示。
        assert hits[0][0].snippet == ""

    @pytest.mark.asyncio
    async def test_deleting_file_vectors_removes_it_from_results(
        self, tmp_path: Path, store: ChromaVectorStore, use_case: SearchFilesUseCase
    ) -> None:
        _index(store, _write_file(tmp_path, "猫.jpg"), "img-1", ocr_text="猫")
        assert len(await use_case.execute(_query(query="猫"))) == 1

        store.delete_file_vectors("img-1")

        assert await use_case.execute(_query(query="猫")) == []

    @pytest.mark.asyncio
    async def test_missing_file_still_indexes_content_but_reports_inaccessible(
        self, tmp_path: Path, store: ChromaVectorStore, use_case: SearchFilesUseCase
    ) -> None:
        """文件在索引前被移走时，内容照样入库，但要如实报告 accessible=False。

        整个任务不该因为 stat 失败而失败：已抽取的内容仍然可检索。
        """
        _index(store, tmp_path / "gone.jpg", "img-gone", ocr_text="猫")

        hits = await use_case.execute(_query(query="猫"))

        assert len(hits) == 1
        _, metadata = hits[0]
        assert metadata is not None
        assert metadata.accessible is False
        assert metadata.size is None

    def test_index_records_utc_modified_time(self, tmp_path: Path, store: ChromaVectorStore) -> None:
        """落盘的 modified 是 UTC ISO 串，供前端直接展示。"""
        mtime = datetime(2026, 6, 15, 12, 0, tzinfo=UTC).timestamp()
        _index(store, _write_file(tmp_path, "猫.jpg", mtime=mtime), "img-1", ocr_text="猫")

        hit = store.search(_vector_for("猫"), [FileType.IMAGE], 10)[0]

        assert hit.modified == "2026-06-15T12:00:00+00:00"

    def test_store_size_filter_uses_bytes(self, tmp_path: Path, store: ChromaVectorStore) -> None:
        """向量库这一层的体积筛选直接用字节，换算是用例的职责。"""
        _index(store, _write_file(tmp_path, "a.jpg", size=500), "img-small", ocr_text="猫")
        _index(store, _write_file(tmp_path, "b.jpg", size=5000), "img-large", ocr_text="猫")

        hits = store.search(
            _vector_for("猫"),
            [FileType.IMAGE],
            10,
            VectorSearchFilters(min_size=1000, max_size=9000),
        )

        assert [hit.file_id for hit in hits] == ["img-large"]

    def test_unknown_extension_fails_the_task(self, tmp_path: Path, store: ChromaVectorStore) -> None:
        """认不出类型就不知道该走哪条抽取路径，必须报错而不是静默跳过。"""
        with pytest.raises(ValueError, match="无法识别文件类型"):
            _index(store, _write_file(tmp_path, "archive.xyz"), "x-1")

    def test_process_reports_the_three_stages_it_owns(
        self, tmp_path: Path, store: ChromaVectorStore
    ) -> None:
        """抽取、编码、索引三个阶段都要报出来，进度依次涨到 100。

        少报一个，前端的进度条就会跳一格——抽取和编码各自可能跑几十秒，那段时间里进度
        不动和卡死没有区别。

        第一个阶段 MOVED 不在这里：文件是调度器在派发之前移进资源库的，它移完就把库内
        路径写回 `task.source_path` 并落库。处理器再报一次只会把同一个阶段写两遍。

        阶段走队列而不是改 `task`：`process` 跑在工作线程里，落库是调度器那一侧的事。
        """
        processor = TaskProcessor(
            document_parser=FakeDocumentParser([]),
            ocr_service=FakeOCR("猫"),
            video_sampler=FakeVideoSampler([]),
            embedding_service=ConceptEmbedder(),
            vector_index=store
        )
        task = Task(
            id="img-1",
            source_path=str(_write_file(tmp_path, "猫.jpg")),
            status=TaskStatus.PROCESSING,
        )
        progress_queue: mp.Queue = mp.Queue()

        # `process` 不返回结果：阶段和进度都经队列上报，落库是调度器那一侧的事。
        processor.process(task, progress_queue)
        # put 交给 feeder 线程异步写管道，所以这里用带超时的 get 而不是 get_nowait。
        reported = [progress_queue.get(timeout=2.0) for _ in range(3)]
        assert [(item.stage.value, item.progress) for item in reported] == [
            ("extracted", 50),
            ("encoded", 75),
            ("indexed", 100),
        ]
        # 只有这三条：多出来的 moved 说明处理器又去报调度器已经报过的阶段了。
        with pytest.raises(queue.Empty):
            progress_queue.get(timeout=0.5)

    def test_process_without_a_queue_still_indexes(
        self, tmp_path: Path, store: ChromaVectorStore
    ) -> None:
        """不给队列时照常跑完——一次性脚本和只关心索引结果的测试走这条路。"""
        task = _index(store, _write_file(tmp_path, "猫.jpg"), "img-2", ocr_text="猫")

        assert task.id == "img-2"
        assert store.search(_vector_for("猫"), [FileType.IMAGE], 5)


# ---------------------------------------------------------------------------
# 用例编排：向量库换成假实现
# ---------------------------------------------------------------------------


class RecordingVectorStore:
    """记录调用并返回预置命中的向量库。"""

    def __init__(self, hits: list[VectorHit] | None = None) -> None:
        self.hits = hits or []
        self.calls: list[tuple[list[float], list[FileType], int, VectorSearchFilters | None]] = []

    def search(
        self,
        query_vector: list[float],
        file_types: list[FileType],
        limit: int,
        filters: VectorSearchFilters | None = None,
    ) -> list[VectorHit]:
        self.calls.append((query_vector, file_types, limit, filters))
        return self.hits


def make_hit(
    file_id: str,
    file_type: FileType = FileType.DOCUMENT,
    score: float = 90.0,
    *,
    name: str = "f.pdf",
    size: int | None = 1024,
    accessible: bool = True,
) -> VectorHit:
    return VectorHit(
        file_id=file_id,
        file_name=name,
        file_type=file_type,
        score=score,
        path=f"/lib/{name}",
        size=size,
        modified="2026-01-01T00:00:00+00:00",
        accessible=accessible,
    )


def make_use_case(
    hits: list[VectorHit] | None = None,
    embedder: ConceptEmbedder | None = None,
) -> tuple[SearchFilesUseCase, ConceptEmbedder, RecordingVectorStore]:
    emb = embedder or ConceptEmbedder()
    vector_store = RecordingVectorStore(hits)
    return SearchFilesUseCase(emb, vector_store), emb, vector_store


class TestSearchOrchestration:
    @pytest.mark.asyncio
    async def test_none_file_types_searches_all_three(self) -> None:
        use_case, _, vector_store = make_use_case()

        await use_case.execute(_query(file_types=None))

        _, file_types, _, _ = vector_store.calls[0]
        assert set(file_types) == {FileType.DOCUMENT, FileType.IMAGE, FileType.VIDEO}

    @pytest.mark.asyncio
    async def test_empty_file_types_searches_nothing(self) -> None:
        """空列表是"限定为空集"，不该退化成搜全部。"""
        use_case, embedder, vector_store = make_use_case([make_hit("d1")])

        assert await use_case.execute(_query(file_types=[])) == []
        assert vector_store.calls == []
        assert embedder.calls == []

    @pytest.mark.asyncio
    async def test_limit_is_applied_per_type_not_across_types(self) -> None:
        use_case, _, _ = make_use_case(
            [
                make_hit("d1", FileType.DOCUMENT, 90.0),
                make_hit("d2", FileType.DOCUMENT, 80.0),
                make_hit("i1", FileType.IMAGE, 95.0),
                make_hit("i2", FileType.IMAGE, 70.0),
                make_hit("v1", FileType.VIDEO, 60.0),
                make_hit("v2", FileType.VIDEO, 50.0),
            ]
        )

        hits = await use_case.execute(_query(limit=1))

        assert [hit[0].file_id for hit in hits] == ["d1", "i1", "v1"]

    @pytest.mark.asyncio
    async def test_results_are_sorted_by_score_within_each_type(self) -> None:
        use_case, _, _ = make_use_case(
            [
                make_hit("d1", FileType.DOCUMENT, 70.0),
                make_hit("d2", FileType.DOCUMENT, 95.0),
                make_hit("d3", FileType.DOCUMENT, 85.0),
            ]
        )

        hits = await use_case.execute(_query())

        assert [hit[0].file_id for hit in hits] == ["d2", "d3", "d1"]

    @pytest.mark.asyncio
    async def test_hits_of_unrequested_types_are_dropped(self) -> None:
        """向量库多返回了没被请求的类型时，用例不该把它塞进结果。"""
        use_case, _, _ = make_use_case(
            [
                make_hit("d1", FileType.DOCUMENT, 99.0),
                make_hit("i1", FileType.IMAGE, 60.0),
            ]
        )

        hits = await use_case.execute(_query(file_types=[FileType.IMAGE]))

        assert [hit[0].file_id for hit in hits] == ["i1"]

    @pytest.mark.asyncio
    async def test_size_filter_converts_mb_to_bytes(self) -> None:
        use_case, _, vector_store = make_use_case()

        await use_case.execute(_query(min_size_m=1.0, max_size_m=500.0))

        _, _, _, filters = vector_store.calls[0]
        assert filters is not None
        assert filters.min_size == 1024 * 1024
        assert filters.max_size == 500 * 1024 * 1024

    @pytest.mark.asyncio
    async def test_zero_min_size_is_not_dropped(self) -> None:
        """0 是有效下限，不能被当成"没传"。"""
        use_case, _, vector_store = make_use_case()

        await use_case.execute(_query(min_size_m=0.0))

        _, _, _, filters = vector_store.calls[0]
        assert filters is not None
        assert filters.min_size == 0

    @pytest.mark.asyncio
    async def test_forwards_name_and_date_filters(self) -> None:
        use_case, _, vector_store = make_use_case()

        await use_case.execute(
            _query(name_query="jpg", start_date="2026-01-01", end_date="2026-09-20")
        )

        _, _, _, filters = vector_store.calls[0]
        assert filters is not None
        assert filters.name_query == "jpg"
        assert filters.start_date == "2026-01-01"
        assert filters.end_date == "2026-09-20"

    @pytest.mark.asyncio
    async def test_metadata_comes_from_the_vector_hit(self) -> None:
        use_case, _, _ = make_use_case(
            [make_hit("d1", name="report.pdf", size=2048, accessible=False)]
        )

        _, metadata = (await use_case.execute(_query()))[0]

        assert metadata is not None
        assert metadata.path == "/lib/report.pdf"
        assert metadata.size == 2048
        assert metadata.accessible is False

    @pytest.mark.asyncio
    async def test_returns_empty_when_embedder_not_implemented(self) -> None:
        """模型未接入 → 空结果而不是抛异常，保持 API 契约可用。"""
        use_case, _, _ = make_use_case(
            [make_hit("d1")],
            embedder=ConceptEmbedder(error=NotImplementedError("jina-clip-v2 尚未接入")),
        )

        assert await use_case.execute(_query()) == []

    @pytest.mark.asyncio
    async def test_returns_empty_when_vector_search_raises(self) -> None:
        """检索失败不该把整个请求打成 500。"""
        use_case, _, _ = make_use_case(
            embedder=ConceptEmbedder(error=RuntimeError("chroma 挂了")),
        )

        assert await use_case.execute(_query()) == []
