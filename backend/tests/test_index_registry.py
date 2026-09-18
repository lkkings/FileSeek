import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from fileseek.db import connect, migrate
from fileseek.index.registry import (
    INDEX_KINDS,
    IndexKind,
    IndexRegistry,
    ModelMismatchError,
)
from fileseek.models.tiers import CPU_BUNDLE, GPU_BUNDLE
from fileseek.models.vectors import normalize


def unit(dimensions: int, axis: int) -> list[float]:
    return normalize([float(n == axis) for n in range(dimensions)])


@pytest.fixture
def db() -> Iterator[sqlite3.Connection]:
    connection = connect(":memory:")
    migrate(connection)
    yield connection
    connection.close()


@pytest.fixture
def registry(tmp_path: Path, db: sqlite3.Connection) -> IndexRegistry:
    return IndexRegistry(tmp_path / "index", db, CPU_BUNDLE)


def test_each_kind_gets_its_own_file(registry: IndexRegistry) -> None:
    paths = {registry.path_for(kind) for kind in INDEX_KINDS}

    assert len(paths) == len(INDEX_KINDS)


def test_document_index_uses_the_text_model_width(registry: IndexRegistry) -> None:
    assert registry.open("document").dimensions == CPU_BUNDLE.text_dimensions


@pytest.mark.parametrize("kind", ["image", "video_segment"])
def test_visual_indexes_use_the_image_model_width(registry: IndexRegistry, kind: IndexKind) -> None:
    assert registry.open(kind).dimensions == CPU_BUNDLE.image_dimensions


def test_indexes_are_independent(registry: IndexRegistry) -> None:
    width = CPU_BUNDLE.image_dimensions
    registry.add("image", [1], [unit(width, 0)])

    assert registry.open("image").size == 1
    assert registry.open("video_segment").size == 0


def test_type_limited_search_only_sees_its_own_index(registry: IndexRegistry) -> None:
    width = CPU_BUNDLE.image_dimensions
    registry.add("image", [1], [unit(width, 0)])
    registry.add("video_segment", [2], [unit(width, 0)])

    hits = registry.search("video_segment", unit(width, 0), limit=10)

    assert [hit.vector_id for hit in hits] == [2]


def test_allocated_ids_start_at_one(registry: IndexRegistry) -> None:
    assert registry.allocate_ids("image", 3) == [1, 2, 3]


def test_allocated_ids_never_repeat(registry: IndexRegistry) -> None:
    first = registry.allocate_ids("image", 2)
    second = registry.allocate_ids("image", 2)

    assert set(first).isdisjoint(second)
    assert second == [3, 4]


def test_ids_are_not_reused_after_removal(registry: IndexRegistry) -> None:
    width = CPU_BUNDLE.image_dimensions
    ids = registry.allocate_ids("image", 2)
    registry.add("image", ids, [unit(width, 0), unit(width, 1)])
    registry.remove("image", ids)

    assert registry.allocate_ids("image", 1) == [3]


def test_id_sequences_are_per_kind(registry: IndexRegistry) -> None:
    assert registry.allocate_ids("image", 2) == [1, 2]
    assert registry.allocate_ids("document", 1) == [1]


def test_allocating_zero_ids_returns_nothing(registry: IndexRegistry) -> None:
    assert registry.allocate_ids("image", 0) == []


def test_negative_id_count_is_rejected(registry: IndexRegistry) -> None:
    with pytest.raises(ValueError, match="must not be negative"):
        registry.allocate_ids("image", -1)


def test_ids_survive_a_reopen(tmp_path: Path, db: sqlite3.Connection) -> None:
    first = IndexRegistry(tmp_path / "index", db, CPU_BUNDLE)
    first.allocate_ids("image", 5)

    second = IndexRegistry(tmp_path / "index", db, CPU_BUNDLE)

    assert second.allocate_ids("image", 1) == [6]


def test_model_is_recorded_on_first_open(registry: IndexRegistry) -> None:
    registry.open("image")

    assert registry.recorded_model("image") == CPU_BUNDLE.image.repo_id
    assert registry.recorded_dimensions("image") == CPU_BUNDLE.image_dimensions


def test_document_index_records_the_text_model(registry: IndexRegistry) -> None:
    registry.open("document")

    assert registry.recorded_model("document") == CPU_BUNDLE.text.repo_id


def test_nothing_recorded_counts_as_compatible(registry: IndexRegistry) -> None:
    assert registry.is_compatible("image") is True
    assert registry.recorded_model("image") is None


def test_switching_tier_is_detected_as_incompatible(tmp_path: Path, db: sqlite3.Connection) -> None:
    IndexRegistry(tmp_path / "index", db, CPU_BUNDLE).open("image")

    after_switch = IndexRegistry(tmp_path / "index", db, GPU_BUNDLE)

    assert after_switch.is_compatible("image") is False


def test_writing_after_a_tier_switch_is_refused(tmp_path: Path, db: sqlite3.Connection) -> None:
    IndexRegistry(tmp_path / "index", db, CPU_BUNDLE).open("image")
    after_switch = IndexRegistry(tmp_path / "index", db, GPU_BUNDLE)

    with pytest.raises(ModelMismatchError, match="Rebuild the index") as excinfo:
        after_switch.add("image", [1], [unit(GPU_BUNDLE.image_dimensions, 0)])

    assert excinfo.value.recorded == CPU_BUNDLE.image.repo_id
    assert excinfo.value.current == GPU_BUNDLE.image.repo_id


def test_unaffected_kinds_stay_usable_after_a_switch(
    tmp_path: Path, db: sqlite3.Connection
) -> None:
    IndexRegistry(tmp_path / "index", db, CPU_BUNDLE).open("image")
    after_switch = IndexRegistry(tmp_path / "index", db, GPU_BUNDLE)

    assert after_switch.is_compatible("document") is True


def test_save_and_reload_keeps_vectors(tmp_path: Path, db: sqlite3.Connection) -> None:
    width = CPU_BUNDLE.image_dimensions
    first = IndexRegistry(tmp_path / "index", db, CPU_BUNDLE)
    first.add("image", [1, 2], [unit(width, 0), unit(width, 1)])
    first.save("image")

    second = IndexRegistry(tmp_path / "index", db, CPU_BUNDLE)

    assert second.open("image").size == 2


def test_search_after_reload_needs_no_recomputation(tmp_path: Path, db: sqlite3.Connection) -> None:
    width = CPU_BUNDLE.image_dimensions
    first = IndexRegistry(tmp_path / "index", db, CPU_BUNDLE)
    first.add("image", [7], [unit(width, 3)])
    first.save_all()

    second = IndexRegistry(tmp_path / "index", db, CPU_BUNDLE)
    hits = second.search("image", unit(width, 3), limit=1)

    assert [hit.vector_id for hit in hits] == [7]


def test_save_all_writes_every_open_index(tmp_path: Path, db: sqlite3.Connection) -> None:
    width = CPU_BUNDLE.image_dimensions
    registry = IndexRegistry(tmp_path / "index", db, CPU_BUNDLE)
    registry.add("image", [1], [unit(width, 0)])
    registry.add("video_segment", [1], [unit(width, 1)])

    written = registry.save_all()

    assert len(written) == 2
    assert all(path.is_file() for path in written)


def test_save_all_with_nothing_open_writes_nothing(registry: IndexRegistry) -> None:
    assert registry.save_all() == []


def test_excluded_ids_are_filtered_from_results(registry: IndexRegistry) -> None:
    width = CPU_BUNDLE.image_dimensions
    registry.add("image", [1, 2, 3], [unit(width, 0), unit(width, 1), unit(width, 2)])

    hits = registry.search("image", unit(width, 0), limit=3, excluded=frozenset({1}))

    assert 1 not in {hit.vector_id for hit in hits}


def test_exclusion_still_fills_the_requested_limit(registry: IndexRegistry) -> None:
    width = CPU_BUNDLE.image_dimensions
    ids = [1, 2, 3, 4]
    registry.add("image", ids, [unit(width, n) for n in range(4)])

    hits = registry.search("image", unit(width, 0), limit=2, excluded=frozenset({1}))

    assert len(hits) == 2
    assert 1 not in {hit.vector_id for hit in hits}


def test_search_without_exclusions_takes_the_plain_path(registry: IndexRegistry) -> None:
    width = CPU_BUNDLE.image_dimensions
    registry.add("image", [1], [unit(width, 0)])

    assert len(registry.search("image", unit(width, 0), limit=1)) == 1


def test_health_reports_a_fresh_index_as_usable(registry: IndexRegistry) -> None:
    health = registry.health("image")

    assert health.is_readable is True
    assert health.is_compatible is True
    assert health.needs_rebuild is False
    assert health.size == 0


def test_health_counts_stored_vectors(registry: IndexRegistry) -> None:
    width = CPU_BUNDLE.image_dimensions
    registry.add("image", [1, 2], [unit(width, 0), unit(width, 1)])
    registry.save("image")

    health = registry.health("image")

    assert health.size == 2
    assert "holds 2 vectors" in health.describe()


def test_health_flags_a_corrupt_file(tmp_path: Path, db: sqlite3.Connection) -> None:
    registry = IndexRegistry(tmp_path / "index", db, CPU_BUNDLE)
    target = registry.path_for("image")
    target.parent.mkdir(parents=True)
    target.write_bytes(b"not an index")

    health = registry.health("image")

    assert health.is_readable is False
    assert health.needs_rebuild is True
    assert "needs rebuilding" in health.describe()


def test_health_flags_a_tier_switch(tmp_path: Path, db: sqlite3.Connection) -> None:
    IndexRegistry(tmp_path / "index", db, CPU_BUNDLE).open("image")

    health = IndexRegistry(tmp_path / "index", db, GPU_BUNDLE).health("image")

    assert health.is_compatible is False
    assert health.needs_rebuild is True
    assert health.recorded_model == CPU_BUNDLE.image.repo_id


def test_health_report_covers_every_kind(registry: IndexRegistry) -> None:
    report = registry.health_report()

    assert [entry.kind for entry in report] == list(INDEX_KINDS)


def test_reset_discards_the_index_file(tmp_path: Path, db: sqlite3.Connection) -> None:
    width = CPU_BUNDLE.image_dimensions
    registry = IndexRegistry(tmp_path / "index", db, CPU_BUNDLE)
    registry.add("image", [1], [unit(width, 0)])
    registry.save("image")

    registry.reset("image")

    assert registry.open("image").size == 0
    assert not registry.path_for("image").is_file()


def test_reset_allows_writing_after_a_tier_switch(tmp_path: Path, db: sqlite3.Connection) -> None:
    """Rebuilding is the documented recovery from a model change."""
    old = IndexRegistry(tmp_path / "index", db, CPU_BUNDLE)
    old.add("image", [1], [unit(CPU_BUNDLE.image_dimensions, 0)])
    old.save("image")

    switched = IndexRegistry(tmp_path / "index", db, GPU_BUNDLE)
    switched.reset("image")
    switched.add("image", [1], [unit(GPU_BUNDLE.image_dimensions, 0)])

    assert switched.open("image").size == 1
    assert switched.is_compatible("image") is True


def test_reset_records_the_new_model(tmp_path: Path, db: sqlite3.Connection) -> None:
    IndexRegistry(tmp_path / "index", db, CPU_BUNDLE).open("image")

    switched = IndexRegistry(tmp_path / "index", db, GPU_BUNDLE)
    switched.reset("image")

    assert switched.recorded_model("image") == GPU_BUNDLE.image.repo_id


def test_rebuild_from_stored_vectors_restores_search(
    tmp_path: Path, db: sqlite3.Connection
) -> None:
    """Deleting the index file must be recoverable, since vectors can be recomputed."""
    width = CPU_BUNDLE.image_dimensions
    registry = IndexRegistry(tmp_path / "index", db, CPU_BUNDLE)
    vectors = [unit(width, 0), unit(width, 1)]
    registry.add("image", [1, 2], vectors)
    registry.save("image")

    registry.path_for("image").unlink()
    rebuilt = IndexRegistry(tmp_path / "index", db, CPU_BUNDLE)
    rebuilt.add("image", [1, 2], vectors)

    assert [hit.vector_id for hit in rebuilt.search("image", vectors[1], limit=1)] == [2]


def test_close_drops_open_handles(registry: IndexRegistry) -> None:
    registry.open("image")

    registry.close()

    assert registry.open("image").size == 0


def test_bundle_is_exposed(registry: IndexRegistry) -> None:
    assert registry.bundle is CPU_BUNDLE
