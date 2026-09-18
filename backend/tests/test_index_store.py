from pathlib import Path

import pytest

from fileseek.db.connection import LocalPathRequiredError
from fileseek.index.store import (
    DimensionMismatchError,
    IndexCorruptError,
    VectorIndex,
)
from fileseek.models.vectors import normalize

RIGHT = normalize([1.0, 0.0, 0.0, 0.0])
UP = normalize([0.0, 1.0, 0.0, 0.0])
DIAGONAL = normalize([1.0, 1.0, 0.0, 0.0])


@pytest.fixture
def index() -> VectorIndex:
    return VectorIndex(dimensions=4)


def test_new_index_is_empty(index: VectorIndex) -> None:
    assert index.size == 0
    assert index.dimensions == 4


def test_dimensions_must_be_positive() -> None:
    with pytest.raises(ValueError, match="must be positive"):
        VectorIndex(dimensions=0)


def test_add_then_search_finds_the_nearest_vector(index: VectorIndex) -> None:
    index.add([10, 20], [RIGHT, UP])

    hits = index.search(RIGHT, limit=1)

    assert [hit.vector_id for hit in hits] == [10]
    assert hits[0].score == pytest.approx(1.0)


def test_search_orders_by_similarity(index: VectorIndex) -> None:
    index.add([10, 20, 30], [RIGHT, DIAGONAL, UP])

    hits = index.search(RIGHT, limit=3)

    assert [hit.vector_id for hit in hits] == [10, 20, 30]
    assert hits[0].score > hits[1].score > hits[2].score


def test_inner_product_of_unit_vectors_is_cosine(index: VectorIndex) -> None:
    index.add([10], [UP])

    hits = index.search(RIGHT, limit=1)

    assert hits[0].score == pytest.approx(0.0, abs=1e-6)


def test_search_on_empty_index_returns_nothing(index: VectorIndex) -> None:
    assert index.search(RIGHT, limit=5) == []


def test_search_limit_beyond_size_is_clamped(index: VectorIndex) -> None:
    index.add([10], [RIGHT])

    assert len(index.search(RIGHT, limit=50)) == 1


def test_search_limit_must_be_positive(index: VectorIndex) -> None:
    index.add([10], [RIGHT])

    with pytest.raises(ValueError, match="limit must be positive"):
        index.search(RIGHT, limit=0)


def test_add_reports_how_many_landed(index: VectorIndex) -> None:
    assert index.add([1, 2], [RIGHT, UP]) == 2
    assert index.size == 2


def test_add_empty_batch_is_a_no_op(index: VectorIndex) -> None:
    assert index.add([], []) == 0
    assert index.size == 0


def test_add_rejects_mismatched_id_count(index: VectorIndex) -> None:
    with pytest.raises(ValueError, match="must match"):
        index.add([1], [RIGHT, UP])


def test_add_rejects_wrong_width(index: VectorIndex) -> None:
    with pytest.raises(DimensionMismatchError) as excinfo:
        index.add([1], [[1.0, 0.0]])

    assert excinfo.value.expected == 4
    assert excinfo.value.received == 2


def test_add_rejects_ragged_batch(index: VectorIndex) -> None:
    with pytest.raises(DimensionMismatchError):
        index.add([1, 2], [RIGHT, [1.0, 0.0]])


def test_search_rejects_wrong_query_width(index: VectorIndex) -> None:
    index.add([1], [RIGHT])

    with pytest.raises(DimensionMismatchError):
        index.search([1.0, 0.0], limit=1)


def test_ids_are_ours_not_insertion_order(index: VectorIndex) -> None:
    index.add([500, 100], [RIGHT, UP])

    assert {hit.vector_id for hit in index.search(RIGHT, limit=2)} == {500, 100}


def test_remove_drops_an_entry(index: VectorIndex) -> None:
    index.add([10, 20], [RIGHT, UP])

    assert index.remove([10]) == 1
    assert index.size == 1
    assert [hit.vector_id for hit in index.search(RIGHT, limit=2)] == [20]


def test_remove_leaves_other_ids_addressable(index: VectorIndex) -> None:
    index.add([10, 20, 30], [RIGHT, DIAGONAL, UP])

    index.remove([20])

    assert index.reconstruct(10) == pytest.approx(list(RIGHT))
    assert index.reconstruct(30) == pytest.approx(list(UP))


def test_remove_unknown_id_removes_nothing(index: VectorIndex) -> None:
    index.add([10], [RIGHT])

    assert index.remove([999]) == 0
    assert index.size == 1


def test_remove_empty_list_is_a_no_op(index: VectorIndex) -> None:
    index.add([10], [RIGHT])

    assert index.remove([]) == 0


def test_reconstruct_returns_the_stored_vector(index: VectorIndex) -> None:
    index.add([10], [DIAGONAL])

    assert index.reconstruct(10) == pytest.approx(list(DIAGONAL))


def test_reconstruct_unknown_id_returns_none(index: VectorIndex) -> None:
    index.add([10], [RIGHT])

    assert index.reconstruct(999) is None


def test_save_and_load_round_trip(tmp_path: Path) -> None:
    index = VectorIndex(dimensions=4)
    index.add([10, 20], [RIGHT, UP])
    target = tmp_path / "index" / "images.faiss"

    index.save(target)
    reloaded = VectorIndex.load(target)

    assert reloaded.size == 2
    assert reloaded.dimensions == 4
    assert [hit.vector_id for hit in reloaded.search(RIGHT, limit=1)] == [10]


def test_reloaded_index_returns_identical_scores(tmp_path: Path) -> None:
    index = VectorIndex(dimensions=4)
    index.add([10, 20, 30], [RIGHT, DIAGONAL, UP])
    before = index.search(DIAGONAL, limit=3)
    target = tmp_path / "images.faiss"
    index.save(target)

    after = VectorIndex.load(target).search(DIAGONAL, limit=3)

    assert [h.vector_id for h in after] == [h.vector_id for h in before]
    assert [h.score for h in after] == pytest.approx([h.score for h in before])


def test_save_creates_the_parent_directory(tmp_path: Path) -> None:
    index = VectorIndex(dimensions=4)
    target = tmp_path / "deep" / "nested" / "images.faiss"

    index.save(target)

    assert target.is_file()


def test_save_leaves_no_staging_file(tmp_path: Path) -> None:
    index = VectorIndex(dimensions=4)
    index.add([1], [RIGHT])

    index.save(tmp_path / "images.faiss")

    assert list(tmp_path.glob("*.writing")) == []


def test_save_replaces_a_previous_version(tmp_path: Path) -> None:
    target = tmp_path / "images.faiss"
    first = VectorIndex(dimensions=4)
    first.add([1], [RIGHT])
    first.save(target)

    second = VectorIndex(dimensions=4)
    second.add([2, 3], [UP, DIAGONAL])
    second.save(target)

    assert VectorIndex.load(target).size == 2


def test_save_rejects_a_network_path() -> None:
    index = VectorIndex(dimensions=4)

    with pytest.raises(LocalPathRequiredError, match="vector index"):
        index.save("//nas/share/images.faiss")


def test_load_rejects_a_network_path() -> None:
    with pytest.raises(LocalPathRequiredError):
        VectorIndex.load("//nas/share/images.faiss")


def test_load_missing_file_is_reported_as_recoverable(tmp_path: Path) -> None:
    with pytest.raises(IndexCorruptError, match="does not exist"):
        VectorIndex.load(tmp_path / "absent.faiss")


def test_load_garbage_file_is_reported_as_corrupt(tmp_path: Path) -> None:
    target = tmp_path / "images.faiss"
    target.write_bytes(b"this is not a faiss index" * 20)

    with pytest.raises(IndexCorruptError) as excinfo:
        VectorIndex.load(target)

    assert excinfo.value.path == target
    assert "rebuilt" in str(excinfo.value)


def test_load_truncated_file_is_reported_as_corrupt(tmp_path: Path) -> None:
    target = tmp_path / "images.faiss"
    index = VectorIndex(dimensions=4)
    index.add([1], [RIGHT])
    index.save(target)
    payload = target.read_bytes()
    target.write_bytes(payload[: len(payload) // 2])

    with pytest.raises(IndexCorruptError):
        VectorIndex.load(target)


def test_load_empty_file_is_reported_as_corrupt(tmp_path: Path) -> None:
    target = tmp_path / "images.faiss"
    target.write_bytes(b"")

    with pytest.raises(IndexCorruptError):
        VectorIndex.load(target)


def test_load_or_create_starts_empty_when_absent(tmp_path: Path) -> None:
    index = VectorIndex.load_or_create(tmp_path / "images.faiss", dimensions=512)

    assert index.size == 0
    assert index.dimensions == 512


def test_load_or_create_reads_an_existing_index(tmp_path: Path) -> None:
    target = tmp_path / "images.faiss"
    original = VectorIndex(dimensions=4)
    original.add([7], [RIGHT])
    original.save(target)

    reopened = VectorIndex.load_or_create(target, dimensions=4)

    assert reopened.size == 1


def test_load_or_create_still_reports_corruption(tmp_path: Path) -> None:
    target = tmp_path / "images.faiss"
    target.write_bytes(b"garbage")

    with pytest.raises(IndexCorruptError):
        VectorIndex.load_or_create(target, dimensions=4)


def test_index_handles_realistic_vector_width() -> None:
    index = VectorIndex(dimensions=512)
    vectors = [normalize([float(n == i) for n in range(512)]) for i in range(5)]
    index.add([1, 2, 3, 4, 5], vectors)

    hits = index.search(vectors[2], limit=1)

    assert hits[0].vector_id == 3
