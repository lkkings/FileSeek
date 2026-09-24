"""单条永久删除的用例。

和清空回收站同一个道理：文件从磁盘消失之后，它的向量也必须消失，否则下次检索还会命中
一个已经不存在的文件。区别在于这里只删一条，所以"只删这一条的向量"是最要紧的断言——
where 条件写宽了会连带清掉别的文件。

索引键是 `file_id`，而回收站条目自己的 `id` 是另一套编号；用错了不会报错，只会一条向量
都删不掉，所以单独立了用例盯着。

前半部分用 mock 验交互（谁被调用、用什么参数、顺序），后半部分开一个真实的 Chroma 库
做往返：先索引、再删除、再检索，确认向量真的没了，且只没了该没的那条。
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from fileseek.features.library.application.commands import DeletePermanentlyCommand
from fileseek.features.library.application.use_cases.delete_recycle_bin import (
    DeleteRecycleUseCase,
)
from fileseek.features.library.domain.entities import RecycleItem
from fileseek.features.library.domain.exceptions import RecycleItemNotFoundError
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
    name: str = "temp.pdf",
    original_path: str | None = None,
    recycle_path: str | None = None,
    file_type: FileType = FileType.DOCUMENT,
    size: int = 4096,
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
    item: RecycleItem | None,
    vector_index: object | None = None,
) -> tuple[DeleteRecycleUseCase, MagicMock, MagicMock, MagicMock]:
    """装好用例，并把它的三个协作者一起返回。

    `MagicMock(spec=...)` 会照着 Protocol 上的 `async def` 自动生成 AsyncMock，
    所以仓储的 await 能正常工作。`item` 传 None 表示条目不存在。
    """
    recycle_repo = AsyncMock(spec=RecycleRepository)
    recycle_repo.get_by_id.return_value = item

    resolver = MagicMock(spec=FileSystemResolver)
    file = MagicMock(spec=FileSystemPort)
    resolver.resolve.return_value = file

    index = vector_index or MagicMock(spec=VectorIndexPort)
    use_case = DeleteRecycleUseCase(recycle_repo, resolver, index)
    return use_case, recycle_repo, resolver, file


@pytest.mark.asyncio
async def test_deletes_both_the_file_and_its_vectors() -> None:
    index = MagicMock(spec=VectorIndexPort)
    item = make_item("r_200", "f_200", recycle_path="/recycle/temp.pdf")
    use_case, recycle_repo, resolver, file = build_use_case(item, index)

    await use_case.execute(DeletePermanentlyCommand("r_200"))

    resolver.resolve.assert_called_once_with("/recycle/temp.pdf")
    file.delete.assert_called_once_with()
    index.delete_file_vectors.assert_called_once_with("f_200")
    recycle_repo.delete.assert_awaited_once_with("r_200")


@pytest.mark.asyncio
async def test_vectors_are_deleted_by_original_file_id_not_item_id() -> None:
    """向量按 `file_id` 落盘，回收站条目的 `id` 是另一套编号。

    传错了不会报错，只会一条向量都删不掉——静默残留，所以单独盯这一条。
    """
    index = MagicMock(spec=VectorIndexPort)
    use_case, *_ = build_use_case(make_item("r_99", "f_7"), index)

    await use_case.execute(DeletePermanentlyCommand("r_99"))

    index.delete_file_vectors.assert_called_once_with("f_7")


@pytest.mark.asyncio
async def test_vectors_are_deleted_before_the_row_is_dropped() -> None:
    """顺序不能反：条目删掉之后就再没有 file_id 可查了。"""
    index = MagicMock(spec=VectorIndexPort)
    use_case, recycle_repo, *_ = build_use_case(make_item(), index)

    order: list[str] = []
    index.delete_file_vectors.side_effect = lambda _file_id: order.append("vectors")
    recycle_repo.delete.side_effect = lambda _item_id: order.append("row")

    await use_case.execute(DeletePermanentlyCommand("r_1"))

    assert order == ["vectors", "row"]


@pytest.mark.asyncio
async def test_file_without_recycle_path_is_deleted_from_its_original_path() -> None:
    """还没被移进回收站目录的条目回退到原路径，向量仍按 file_id 删。"""
    index = MagicMock(spec=VectorIndexPort)
    item = make_item("r_1", "f_1", name="report.pdf", recycle_path=None)
    use_case, _repo, resolver, file = build_use_case(item, index)

    await use_case.execute(DeletePermanentlyCommand("r_1"))

    resolver.resolve.assert_called_once_with("/library/report.pdf")
    file.delete.assert_called_once_with()
    index.delete_file_vectors.assert_called_once_with("f_1")


@pytest.mark.asyncio
async def test_missing_item_touches_nothing() -> None:
    """条目不存在时不能顺手删向量：拿不到 file_id，删什么都是猜的。"""
    index = MagicMock(spec=VectorIndexPort)
    use_case, recycle_repo, resolver, _file = build_use_case(None, index)

    with pytest.raises(RecycleItemNotFoundError, match="回收站条目 r_missing 不存在"):
        await use_case.execute(DeletePermanentlyCommand("r_missing"))

    resolver.resolve.assert_not_called()
    index.delete_file_vectors.assert_not_called()
    recycle_repo.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_failing_vector_delete_does_not_abort_the_deletion() -> None:
    """向量库是派生索引，文件此刻已经删了。

    抛出去只会让条目留在回收站里指向一个不存在的文件，而用户没有别的补救入口。
    """
    index = MagicMock(spec=VectorIndexPort)
    index.delete_file_vectors.side_effect = RuntimeError("chroma down")
    use_case, recycle_repo, _resolver, file = build_use_case(make_item("r_1", "f_1"), index)

    await use_case.execute(DeletePermanentlyCommand("r_1"))

    file.delete.assert_called_once_with()
    recycle_repo.delete.assert_awaited_once_with("r_1")


@pytest.mark.asyncio
async def test_the_failure_is_logged_with_the_file_id(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """吞掉异常的前提是留下可查的日志，否则残留向量没人知道。"""
    index = MagicMock(spec=VectorIndexPort)
    index.delete_file_vectors.side_effect = RuntimeError("chroma down")
    use_case, *_ = build_use_case(make_item("r_1", "f_42"), index)

    with caplog.at_level("ERROR"):
        await use_case.execute(DeletePermanentlyCommand("r_1"))

    assert "f_42" in caplog.text


@pytest.mark.asyncio
async def test_a_failing_file_delete_stops_the_deletion() -> None:
    """文件删不掉是真故障（权限、占用），不能当无事发生。

    此时向量不删、行也不删——条目留在回收站里还能重试。
    """
    index = MagicMock(spec=VectorIndexPort)
    use_case, recycle_repo, _resolver, file = build_use_case(make_item(), index)
    file.delete.side_effect = PermissionError("file in use")

    with pytest.raises(PermissionError):
        await use_case.execute(DeletePermanentlyCommand("r_1"))

    index.delete_file_vectors.assert_not_called()
    recycle_repo.delete.assert_not_awaited()


class TestAgainstARealVectorStore:
    """开一个真的 Chroma 库，验删除之后检索真的不再命中。

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
    async def test_deleting_removes_the_vectors_from_every_collection(
        self, tmp_path: Path
    ) -> None:
        store = ChromaVectorStore(tmp_path / "vectors")
        self.index_all_three_types(store, "f_1")
        assert self.found_ids(store) == {"f_1"}

        use_case, *_ = build_use_case(make_item("r_1", "f_1"), store)
        await use_case.execute(DeletePermanentlyCommand("r_1"))

        assert self.found_ids(store) == set()

    @pytest.mark.asyncio
    async def test_only_that_one_file_loses_its_vectors(self, tmp_path: Path) -> None:
        """最要紧的一条：单条删除只能动这一条，不能连带清掉别的文件。"""
        store = ChromaVectorStore(tmp_path / "vectors")
        for file_id in ("f_1", "f_2", "f_3"):
            self.index_all_three_types(store, file_id)
        assert self.found_ids(store) == {"f_1", "f_2", "f_3"}

        use_case, *_ = build_use_case(make_item("r_2", "f_2"), store)
        await use_case.execute(DeletePermanentlyCommand("r_2"))

        assert self.found_ids(store) == {"f_1", "f_3"}

    @pytest.mark.asyncio
    async def test_deleting_twice_is_harmless(self, tmp_path: Path) -> None:
        """向量已经没了再删一次不该报错——删除请求可能被重试。"""
        store = ChromaVectorStore(tmp_path / "vectors")
        self.index_all_three_types(store, "f_1")

        for _ in range(2):
            use_case, *_ = build_use_case(make_item("r_1", "f_1"), store)
            await use_case.execute(DeletePermanentlyCommand("r_1"))

        assert self.found_ids(store) == set()

    @pytest.mark.asyncio
    async def test_a_file_with_no_vectors_indexed_deletes_cleanly(self, tmp_path: Path) -> None:
        """入库任务还没跑完就被删的文件，回收站里有行、向量库里没有对应记录。"""
        store = ChromaVectorStore(tmp_path / "vectors")
        self.index_all_three_types(store, "f_keep")

        use_case, recycle_repo, *_ = build_use_case(make_item("r_1", "f_never_indexed"), store)
        await use_case.execute(DeletePermanentlyCommand("r_1"))

        recycle_repo.delete.assert_awaited_once_with("r_1")
        assert self.found_ids(store) == {"f_keep"}

    @pytest.mark.asyncio
    async def test_vectors_stay_gone_after_reopening_the_store(self, tmp_path: Path) -> None:
        """删除要落盘：重开同一目录不该又把向量读回来。"""
        vector_dir = tmp_path / "vectors"
        store = ChromaVectorStore(vector_dir)
        self.index_all_three_types(store, "f_1")
        self.index_all_three_types(store, "f_keep")

        use_case, *_ = build_use_case(make_item("r_1", "f_1"), store)
        await use_case.execute(DeletePermanentlyCommand("r_1"))

        assert self.found_ids(ChromaVectorStore(vector_dir)) == {"f_keep"}
