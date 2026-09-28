from pathlib import Path

from fileseek.infrastructure.thumbnail_cache import ThumbnailCache


def test_repeated_requests_reuse_cached_bytes(tmp_path: Path):
    cache = ThumbnailCache(tmp_path / "thumbnails")
    metadata = {
        "file_id": "file-1",
        "source_size": 120,
        "source_modified": "2026-09-28T08:00:00Z",
        "size": "list",
    }

    cache.store(data=b"cached-bytes", **metadata)
    cached = cache.get(**metadata)
    cached_again = cache.get(**metadata)

    assert cached == b"cached-bytes"
    assert cached_again == cached
    assert list((tmp_path / "thumbnails").iterdir()) == list((tmp_path / "thumbnails").iterdir())


def test_changed_file_metadata_uses_a_different_cache_entry(tmp_path: Path):
    cache = ThumbnailCache(tmp_path / "thumbnails")
    original_metadata = {
        "file_id": "file-1",
        "source_size": 120,
        "source_modified": "2026-09-28T08:00:00Z",
        "size": "list",
    }
    changed_metadata = {
        **original_metadata,
        "source_modified": "2026-09-28T09:00:00Z",
    }
    cache.store(data=b"old-thumbnail", **original_metadata)

    assert cache.get(**original_metadata) == b"old-thumbnail"
    assert cache.get(**changed_metadata) is None


def test_list_and_detail_sizes_are_cached_separately(tmp_path: Path):
    cache = ThumbnailCache(tmp_path / "thumbnails")
    common_metadata = {
        "file_id": "file-1",
        "source_size": 120,
        "source_modified": "2026-09-28T08:00:00Z",
    }

    cache.store(size="list", data=b"list-thumbnail", **common_metadata)
    cache.store(size="detail", data=b"detail-thumbnail", **common_metadata)

    assert cache.get(size="list", **common_metadata) == b"list-thumbnail"
    assert cache.get(size="detail", **common_metadata) == b"detail-thumbnail"


def test_missing_cache_entry_returns_none(tmp_path: Path):
    cache = ThumbnailCache(tmp_path / "thumbnails")

    assert cache.get(
        file_id="missing",
        source_size=10,
        source_modified="2026-09-28T08:00:00Z",
        size="list",
    ) is None
