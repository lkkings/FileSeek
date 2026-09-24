"""清空回收站的用例。

清空回收站是唯一一处"文件彻底消失"的入口，所以它也是向量必须跟着消失的地方：留下的
向量下次检索还会命中一个已经不存在的文件。索引键是 `file_id`，而回收站条目自己的 `id`
是另一套编号，用错了就会删不掉任何东西——这一点单独立了用例盯着。

前半部分用 mock 验交互（谁被调用、用什么参数、顺序），后半部分开一个真实的 Chroma
库做往返：先索引、再清空、再检索，确认向量真的没了，且只没了该没的那些。
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, call

import pytest

from fileseek.features.library.application.commands import ClearRecycleBinCommand
from fileseek.features.library.application.use_cases.clear_all_recycle_bin import (
    ClearRecycleBinUseCase,
)
from fileseek.features.library.domain.entities import RecycleItem
from fileseek.features.library.domain.repositories import RecycleRepository
from fileseek.features.tasks.domain.ports import IndexedFileMetadata, VectorIndexPort
from fileseek.features.tasks.infrastructure.vector_store.chroma_store import (
    ChromaVectorStore,
)
from fileseek.shared.domain.file_types import FileType
from fileseek.shared.domain.ports import FileSystemPort, FileSystemResolver

# 索引和查询用同一个向量，检索必然命中——这里验的是"还在不在"，不是相似度。
HIT = [1.0, 0.0, 0.0, 0.0]


def make_item(
    item_id: str = "r_1",
    original_file_id: str = "f_1",
    *,
    name: str = "1.png",
    original_path: str | None = None,
    recycle_path: str | None = None,
    file_type: FileType = FileType.IMAGE,
    size: int = 100,
) -> RecycleItem:
    return RecycleItem(
        id=item_id,
        original_file_id=original_file_id,
        original_name=name,
        original_path=original_path or f"/library/{name}",
        deleted_at="2026-01-01T00:00:00+00:00",
        file_type=file_type,
        size=size,
        recycle_path=recycle_path,
    )


def build_use_case(
    items: list[RecycleItem],
    vector_index: object | None = None,
) -> tuple[ClearRecycleBinUseCase, MagicMock, MagicMock, list[MagicMock]]:
    """装好用例，并把它的三个协作者一起返回。

    `MagicMock(spec=...)` 会照着 Protocol 上的 `async def` 自动生成 AsyncMock，
    所以仓储的 await 能正常工作。
    """
    recycle_repo = AsyncMock(spec=RecycleRepository)
    recycle_repo.list_all_items.return_value = items

    resolver = MagicMock(spec=FileSystemResolver)
    files = [MagicMock(spec=FileSystemPort) for _ in items]
    resolver.resolve.side_effect = files

    index = vector_index or MagicMock(spec=VectorIndexPort)
    use_case = ClearRecycleBinUseCase(recycle_repo, resolver, index)
    return use_case, recycle_repo, resolver, files


@pytest.mark.asyncio
async def test_clears_both_the_files_and_their_vectors() -> None:
    items = [make_item("r_1", "f_1", name="1.png"), make_item("r_2", "f_2", name="2.png")]
    index = MagicMock(spec=VectorIndexPort)
    use_case, recycle_repo, resolver, files = build_use_case(items, index)

    await use_case.execute(ClearRecycleBinCommand())

    resolver.resolve.assert_any_call("/library/1.png")
    resolver.resolve.assert_any_call("/library/2.png")
    for file in files:
        file.delete.assert_called_once_with()

    assert index.delete_file_vectors.call_args_list == [call("f_1"), call("f_2")]
    recycle_repo.delete_all.assert_awaited_once()


@pytest.mark.asyncio
async def test_vectors_are_deleted_by_original_file_id_not_item_id() -> None:
    """向量按 `file_id` 落盘，回收站条目的 `id` 是另一套编号。

    传错了不会报错，只会一条向量都删不掉——静默残留，所以单独盯这一条。
    """
    index = MagicMock(spec=VectorIndexPort)
    use_case, *_ = build_use_case([make_item("r_99", "f_7")], index)

    await use_case.execute(ClearRecycleBinCommand())

    index.delete_file_vectors.assert_called_once_with("f_7")


@pytest.mark.asyncio
async def test_vectors_are_deleted_before_the_rows_are_dropped() -> None:
    """顺序不能反：`delete_all` 之后就再没有 file_id 可查了。"""
    index = MagicMock(spec=VectorIndexPort)
    use_case, recycle_repo, *_ = build_use_case([make_item()], index)

    order: list[str] = []
    index.delete_file_vectors.side_effect = lambda _file_id: order.append("vectors")
    recycle_repo.delete_all.side_effect = lambda: order.append("rows")

    await use_case.execute(ClearRecycleBinCommand())

    assert order == ["vectors", "rows"]


@pytest.mark.asyncio
async def test_file_is_deleted_from_its_recycle_path_when_it_has_one() -> None:
    """文件已被移进回收站目录时删的是那份副本，向量仍按原 file_id 删。"""
    index = MagicMock(spec=VectorIndexPort)
    item = make_item("r_1", "f_1", recycle_path="/recycle/r_1.png")
    use_case, _repo, resolver, files = build_use_case([item], index)

    await use_case.execute(ClearRecycleBinCommand())

    resolver.resolve.assert_called_once_with("/recycle/r_1.png")
    files[0].delete.assert_called_once_with()
    index.delete_file_vectors.assert_called_once_with("f_1")


@pytest.mark.asyncio
async def test_empty_recycle_bin_deletes_nothing() -> None:
    index = MagicMock(spec=VectorIndexPort)
    use_case, recycle_repo, resolver, _files = build_use_case([], index)

    await use_case.execute(ClearRecycleBinCommand())

    resolver.resolve.assert_not_called()
    index.delete_file_vectors.assert_not_called()
    # 条目为空也照常调用：幂等，且省掉一个分支。
    recycle_repo.delete_all.assert_awaited_once()


@pytest.mark.asyncio
async def test_a_failing_vector_delete_does_not_abort_the_clear() -> None:
    """向量库是派生索引，文件此刻已经删了——抛出去只会让回收站永远清不干净。

    所以第一条失败后剩下的条目照样处理，`delete_all` 照样执行。
    """
    index = MagicMock(spec=VectorIndexPort)
    index.delete_file_vectors.side_effect = [RuntimeError("chroma down"), None]
    items = [make_item("r_1", "f_1"), make_item("r_2", "f_2", name="2.png")]
    use_case, recycle_repo, _resolver, files = build_use_case(items, index)

    await use_case.execute(ClearRecycleBinCommand())

    assert index.delete_file_vectors.call_args_list == [call("f_1"), call("f_2")]
    for file in files:
        file.delete.assert_called_once_with()
    recycle_repo.delete_all.assert_awaited_once()


@pytest.mark.asyncio
async def test_the_failure_is_logged_with_the_file_id(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """吞掉异常的前提是留下可查的日志，否则残留向量没人知道。"""
    index = MagicMock(spec=VectorIndexPort)
    index.delete_file_vectors.side_effect = RuntimeError("chroma down")
    use_case, *_ = build_use_case([make_item("r_1", "f_42")], index)

    with caplog.at_level("ERROR"):
        await use_case.execute(ClearRecycleBinCommand())

    assert "f_42" in caplog.text


@pytest.mark.asyncio
async def test_a_failing_file_delete_stops_the_clear() -> None:
    """文件删不掉是真故障（权限、占用），不能当无事发生。

    此时该条目的向量不删、行也不删——下次清空还能重试。
    """
    index = MagicMock(spec=VectorIndexPort)
    use_case, recycle_repo, _resolver, files = build_use_case([make_item()], index)
    files[0].delete.side_effect = PermissionError("file in use")

    with pytest.raises(PermissionError):
        await use_case.execute(ClearRecycleBinCommand())

    index.delete_file_vectors.assert_not_called()
    recycle_repo.delete_all.assert_not_awaited()


class TestAgainstARealVectorStore:
    """开一个真的 Chroma 库，验清空之后检索真的不再命中。

    mock 只能证明"调了删除"，证明不了删除有效果：`delete_file_vectors` 的 where 条件
    写错、或者索引键对不上，mock 全都看不出来。
    """

    @staticmethod
    def metadata(file_id: str, name: str) -> IndexedFileMetadata:
        return IndexedFileMetadata(
            file_id=file_id,
            file_name=name,
            path=f"/library/{name}",
            size=1024,
            modified="2026-01-01T00:00:00+00:00",
            modified_ts=1767225600.0,
            accessible=True,
        )

    def index_all_three_types(self, store: ChromaVectorStore, file_id: str) -> None:
        """同一个 file_id 在三个 collection 里都留下向量。"""
        store.add_document_vectors(
            self.metadata(file_id, f"{file_id}.pdf"),
            [{"embedding": HIT, "page_number": 1, "line_number": 2, "text": "季度营收"}],
        )
        store.add_image_vectors(
            self.metadata(file_id, f"{file_id}.png"),
            [{"embedding": HIT, "feature_type": "ocr", "text": "猫咪"}],
        )
        store.add_video_vectors(
            self.metadata(file_id, f"{file_id}.mp4"),
            [{"embedding": HIT, "start_time": 83.0, "end_time": 120.0}],
        )

    @staticmethod
    def found_ids(store: ChromaVectorStore) -> set[str]:
        hits = store.search(HIT, [FileType.DOCUMENT, FileType.IMAGE, FileType.VIDEO], 50)
        return {hit.file_id for hit in hits}

    @pytest.mark.asyncio
    async def test_clearing_removes_the_vectors_from_every_collection(
        self, tmp_path: Path
    ) -> None:
        store = ChromaVectorStore(tmp_path / "vectors")
        self.index_all_three_types(store, "f_1")
        assert self.found_ids(store) == {"f_1"}

        use_case, *_ = build_use_case([make_item("r_1", "f_1")], store)
        await use_case.execute(ClearRecycleBinCommand())

        assert self.found_ids(store) == set()

    @pytest.mark.asyncio
    async def test_only_the_recycled_files_lose_their_vectors(self, tmp_path: Path) -> None:
        """最要紧的一条：删的是 file_id 指定的那些，不是整库。"""
        store = ChromaVectorStore(tmp_path / "vectors")
        for file_id in ("f_1", "f_2", "f_keep"):
            self.index_all_three_types(store, file_id)
        assert self.found_ids(store) == {"f_1", "f_2", "f_keep"}

        items = [make_item("r_1", "f_1"), make_item("r_2", "f_2", name="2.png")]
        use_case, *_ = build_use_case(items, store)
        await use_case.execute(ClearRecycleBinCommand())

        assert self.found_ids(store) == {"f_keep"}

    @pytest.mark.asyncio
    async def test_clearing_twice_is_harmless(self, tmp_path: Path) -> None:
        """向量已经没了再删一次不该报错——回收站清空可能被重试。"""
        store = ChromaVectorStore(tmp_path / "vectors")
        self.index_all_three_types(store, "f_1")

        for _ in range(2):
            use_case, *_ = build_use_case([make_item("r_1", "f_1")], store)
            await use_case.execute(ClearRecycleBinCommand())

        assert self.found_ids(store) == set()

    @pytest.mark.asyncio
    async def test_a_file_with_no_vectors_indexed_clears_cleanly(self, tmp_path: Path) -> None:
        """入库任务还没跑完就被删的文件，回收站里有行、向量库里没有对应记录。"""
        store = ChromaVectorStore(tmp_path / "vectors")
        self.index_all_three_types(store, "f_keep")

        use_case, recycle_repo, _resolver, _files = build_use_case(
            [make_item("r_1", "f_never_indexed")], store
        )
        await use_case.execute(ClearRecycleBinCommand())

        recycle_repo.delete_all.assert_awaited_once()
        assert self.found_ids(store) == {"f_keep"}

    @pytest.mark.asyncio
    async def test_vectors_stay_gone_after_reopening_the_store(self, tmp_path: Path) -> None:
        """删除要落盘：重开同一目录不该又把向量读回来。"""
        vector_dir = tmp_path / "vectors"
        store = ChromaVectorStore(vector_dir)
        self.index_all_three_types(store, "f_1")

        use_case, *_ = build_use_case([make_item("r_1", "f_1")], store)
        await use_case.execute(ClearRecycleBinCommand())

        assert self.found_ids(ChromaVectorStore(vector_dir)) == set()
