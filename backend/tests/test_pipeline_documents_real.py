"""Tests the document pipeline against the real models.

Marked slow and skipped when weights are absent. The fast tests use a keyword
encoder, which proves the chunk/index/search wiring but cannot prove the claim the
spec actually makes: that a document is reachable by a natural-language query
describing its topic, in words that never appear in it. Only the real text encoder
can show that. Likewise, faked recognition proves the OCR fallback is *wired*;
only RapidOCR reading real rendered pixels proves a scan becomes searchable.
"""

from __future__ import annotations

import io
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont

from fileseek.db import (
    ChunkRepository,
    DocumentRepository,
    FileRepository,
    ImageRepository,
    SegmentRepository,
    VideoRepository,
    connect,
    migrate,
)
from fileseek.index.registry import IndexRegistry
from fileseek.library.layout import LibraryLayout
from fileseek.models.encoders import LocalEncoders
from fileseek.models.hardware import HardwareProfile
from fileseek.models.tiers import CPU_BUNDLE, ModelSelection
from fileseek.models.weights import WeightStore
from fileseek.pipeline.context import IndexingContext
from fileseek.pipeline.documents import index_document

from doc_fixtures import write_scanned_pdf

pytestmark = pytest.mark.slow

SELECTION = ModelSelection(tier="cpu", device="cpu", reason="test", profile=HardwareProfile())

_CANDIDATE_DIRS = (
    Path("D:/FileSeek/.models"),
    Path(__file__).resolve().parents[2] / ".models",
)

_FONT_CANDIDATES = (
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
)

# Two documents on unrelated topics. The query below shares no wording with
# either, so reaching the right one is a semantic result, not a keyword match.
ML_DOCUMENT = (
    "本文介绍卷积神经网络的训练方法。我们使用反向传播算法调整权重，"
    "并在图像分类任务上评估模型的准确率。实验表明，增加网络深度可以提升表现，"
    "但也会带来梯度消失的问题。为此我们引入残差连接来缓解该现象。"
)

COOKING_DOCUMENT = (
    "这道红烧肉的做法很简单。先把五花肉切成方块，用冷水焯去血沫，"
    "然后加入冰糖炒出糖色，倒入酱油和料酒，最后小火慢炖一个小时。"
    "出锅前撒上葱花，肉质软烂入味，配米饭非常好吃。"
)


def _weight_store() -> WeightStore | None:
    for candidate in _CANDIDATE_DIRS:
        store = WeightStore(candidate)
        if store.readiness(CPU_BUNDLE).is_ready:
            return store
    return None


@pytest.fixture(scope="module")
def encoders() -> LocalEncoders:
    store = _weight_store()
    if store is None:
        pytest.skip("CPU tier weights are not on disk")
    return LocalEncoders(SELECTION, store)


@pytest.fixture
def db() -> Iterator[sqlite3.Connection]:
    connection = connect(":memory:")
    migrate(connection)
    yield connection
    connection.close()


@pytest.fixture
def context(tmp_path: Path, db: sqlite3.Connection, encoders: LocalEncoders) -> IndexingContext:
    return IndexingContext(
        layout=LibraryLayout(root=tmp_path / "library").initialize(),
        files=FileRepository(db),
        images=ImageRepository(db),
        documents=DocumentRepository(db),
        videos=VideoRepository(db),
        segments=SegmentRepository(db),
        chunks=ChunkRepository(db),
        registry=IndexRegistry(tmp_path / "index", db, CPU_BUNDLE),
        encoder=encoders,
    )


@pytest.fixture
def incoming(tmp_path: Path) -> Path:
    directory = tmp_path / "downloads"
    directory.mkdir()
    return directory


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in _FONT_CANDIDATES:
        if Path(candidate).is_file():
            return ImageFont.truetype(candidate, size)
    pytest.skip("no CJK font available to render a scan")


def _page_image(lines: list[str], size: tuple[int, int] = (1000, 400)) -> bytes:
    """Render text to a page image, which is what a scanner would hand us."""
    image = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(image)
    font = _font(44)
    for index, line in enumerate(lines):
        draw.text((40, 40 + index * 70), line, fill="black", font=font)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _write(directory: Path, name: str, body: str) -> Path:
    path = directory / name
    path.write_text(body, encoding="utf-8")
    return path


def _file_ids_for(context: IndexingContext, query: str, limit: int = 5) -> list[str]:
    """Run a natural-language query and resolve the hits back to files."""
    vector = context.encoder.encode_text_query(query)  # type: ignore[attr-defined]
    hits = context.registry.search("document", vector, limit=limit)
    return [
        chunk.file_id for chunk in context.chunks.get_by_vector_ids([h.vector_id for h in hits])
    ]


# --- 8.3: a natural-language topic query reaches the document ----------------


def test_a_topic_query_reaches_the_right_document(context: IndexingContext, incoming: Path) -> None:
    """The words of the query appear in neither document; only the topic matches."""
    paper = index_document(_write(incoming, "paper.txt", ML_DOCUMENT), context)
    index_document(_write(incoming, "recipe.txt", COOKING_DOCUMENT), context)

    found = _file_ids_for(context, "深度学习模型是怎么优化的？")

    assert found, "the query returned no hits at all"
    assert found[0] == paper.record.id


def test_a_query_about_the_other_topic_reaches_the_other_document(
    context: IndexingContext, incoming: Path
) -> None:
    """The discriminating half: the same index must not answer everything alike."""
    index_document(_write(incoming, "paper.txt", ML_DOCUMENT), context)
    recipe = index_document(_write(incoming, "recipe.txt", COOKING_DOCUMENT), context)

    found = _file_ids_for(context, "怎么炖出好吃的猪肉？")

    assert found
    assert found[0] == recipe.record.id


def test_an_english_query_reaches_a_chinese_document(
    context: IndexingContext, incoming: Path
) -> None:
    """The text model is multilingual, which is why cross-language search works."""
    paper = index_document(_write(incoming, "paper.txt", ML_DOCUMENT), context)
    index_document(_write(incoming, "recipe.txt", COOKING_DOCUMENT), context)

    found = _file_ids_for(context, "how are neural networks trained?")

    assert found
    assert found[0] == paper.record.id


# --- 8.4: OCR fallback, read from real pixels -------------------------------


def test_a_real_scan_is_read_by_recognition(context: IndexingContext, incoming: Path) -> None:
    """No text layer at all: the words have to come out of the rendered pixels."""
    scan = write_scanned_pdf(
        incoming / "scan.pdf", [_page_image(["深度学习与神经网络", "图像分类实验报告"])]
    )

    result = index_document(scan, context)

    assert result.used_recognition
    assert result.is_searchable_by_content
    stored = context.documents.get(result.record.id)
    assert stored is not None
    assert stored.text_source == "ocr"
    # Compared in-process: the console mangles CJK, so reading it off stdout lies.
    assert "深度学习" in (stored.text_content or "")


def test_a_recognized_scan_answers_a_topic_query(context: IndexingContext, incoming: Path) -> None:
    """The whole point of the fallback: a scan becomes findable by its content."""
    scan = write_scanned_pdf(
        incoming / "scan.pdf", [_page_image(["深度学习与神经网络", "图像分类实验报告"])]
    )
    result = index_document(scan, context)

    found = _file_ids_for(context, "神经网络的图像识别")

    assert found
    assert found[0] == result.record.id
