import sqlite3
from collections.abc import Iterator

import pytest

from fileseek.db import (
    ChunkRecord,
    ChunkRepository,
    FileRecord,
    FileRepository,
    SegmentRecord,
    SegmentRepository,
    connect,
    migrate,
)


@pytest.fixture
def db() -> Iterator[sqlite3.Connection]:
    connection = connect(":memory:")
    migrate(connection)
    yield connection
    connection.close()


@pytest.fixture
def files(db: sqlite3.Connection) -> FileRepository:
    return FileRepository(db)


@pytest.fixture
def segments(db: sqlite3.Connection) -> SegmentRepository:
    return SegmentRepository(db)


@pytest.fixture
def chunks(db: sqlite3.Connection) -> ChunkRepository:
    return ChunkRepository(db)


def make_file(
    file_id: str = "f1",
    *,
    path: str | None = None,
    filename: str = "a.jpg",
    media_type: str = "image",
    content_hash: str | None = None,
    index_state: str = "pending",
) -> FileRecord:
    return FileRecord(
        id=file_id,
        path=path if path is not None else f"/library/images/{file_id}.jpg",
        filename=filename,
        media_type=media_type,  # type: ignore[arg-type]
        size=1024,
        content_hash=content_hash if content_hash is not None else f"hash-{file_id}",
        added_at=1_700_000_000,
        created_at=1_699_000_000,
        modified_at=1_699_500_000,
        index_state=index_state,  # type: ignore[arg-type]
    )


def add_video(files: FileRepository, db: sqlite3.Connection, video_id: str = "v1") -> None:
    files.add(
        make_file(
            video_id,
            path=f"/library/videos/{video_id}.mp4",
            filename=f"{video_id}.mp4",
            media_type="video",
        )
    )
    db.execute(
        "INSERT INTO videos (file_id, duration, width, height, fps) VALUES (?, ?, ?, ?, ?)",
        (video_id, 600.0, 1920, 1080, 25.0),
    )


def add_document(files: FileRepository, db: sqlite3.Connection, file_id: str = "d1") -> None:
    files.add(
        make_file(
            file_id,
            path=f"/library/documents/{file_id}.pdf",
            filename=f"{file_id}.pdf",
            media_type="document",
        )
    )
    db.execute(
        "INSERT INTO documents (file_id, text_content, page_count) VALUES (?, ?, ?)",
        (file_id, "deep learning survey", 10),
    )


def test_add_then_get_round_trips(files: FileRepository) -> None:
    record = files.add(make_file())

    assert files.get("f1") == record


def test_get_unknown_id_returns_none(files: FileRepository) -> None:
    assert files.get("missing") is None


def test_get_by_content_hash(files: FileRepository) -> None:
    files.add(make_file("f1", content_hash="abc"))

    found = files.get_by_content_hash("abc")

    assert found is not None
    assert found.id == "f1"


def test_get_by_content_hash_unknown_returns_none(files: FileRepository) -> None:
    assert files.get_by_content_hash("nope") is None


def test_get_by_path(files: FileRepository) -> None:
    files.add(make_file("f1", path="/library/images/one.jpg"))

    found = files.get_by_path("/library/images/one.jpg")

    assert found is not None
    assert found.id == "f1"


def test_get_by_path_unknown_returns_none(files: FileRepository) -> None:
    assert files.get_by_path("/nowhere.jpg") is None


def test_get_many_preserves_requested_order(files: FileRepository) -> None:
    for file_id in ("f1", "f2", "f3"):
        files.add(make_file(file_id))

    found = files.get_many(["f3", "f1", "f2"])

    assert [record.id for record in found] == ["f3", "f1", "f2"]


def test_get_many_skips_unknown_ids(files: FileRepository) -> None:
    files.add(make_file("f1"))

    found = files.get_many(["f1", "ghost"])

    assert [record.id for record in found] == ["f1"]


def test_get_many_with_empty_input(files: FileRepository) -> None:
    assert files.get_many([]) == []


def test_get_many_spans_variable_limit(files: FileRepository) -> None:
    ids = [f"f{n}" for n in range(1000)]
    for file_id in ids:
        files.add(make_file(file_id))

    found = files.get_many(ids)

    assert len(found) == 1000


def test_add_records_origin_path(files: FileRepository) -> None:
    files.add(make_file(), original_path="D:/downloads/a.jpg")

    assert files.origins("f1") == ["D:/downloads/a.jpg"]


def test_add_without_origin_records_none(files: FileRepository) -> None:
    files.add(make_file())

    assert files.origins("f1") == []


def test_repeated_submission_appends_origin(files: FileRepository) -> None:
    files.add(make_file(), original_path="D:/downloads/a.jpg")

    files.add_origin("f1", "E:/backup/a.jpg", recorded_at=1_700_000_100)

    assert files.origins("f1") == ["D:/downloads/a.jpg", "E:/backup/a.jpg"]


def test_duplicate_origin_is_not_recorded_twice(files: FileRepository) -> None:
    files.add(make_file(), original_path="D:/downloads/a.jpg")

    files.add_origin("f1", "D:/downloads/a.jpg", recorded_at=1_700_000_200)

    assert files.origins("f1") == ["D:/downloads/a.jpg"]


def test_list_by_media_type_filters_and_orders(files: FileRepository) -> None:
    files.add(make_file("i1", media_type="image"))
    files.add(make_file("v1", path="/library/videos/v1.mp4", media_type="video"))

    found = files.list_by_media_type("image")

    assert [record.id for record in found] == ["i1"]


def test_list_by_media_type_honours_limit(files: FileRepository) -> None:
    for file_id in ("a", "b", "c"):
        files.add(make_file(file_id))

    assert len(files.list_by_media_type("image", limit=2)) == 2


def test_list_by_index_state(files: FileRepository) -> None:
    files.add(make_file("f1", index_state="indexed"))
    files.add(make_file("f2", index_state="missing"))

    found = files.list_by_index_state("missing")

    assert [record.id for record in found] == ["f2"]


def test_set_index_state_updates_row(files: FileRepository) -> None:
    files.add(make_file())

    assert files.set_index_state("f1", "indexed") is True
    record = files.get("f1")
    assert record is not None
    assert record.index_state == "indexed"


def test_set_index_state_on_unknown_id_reports_false(files: FileRepository) -> None:
    assert files.set_index_state("ghost", "indexed") is False


def test_delete_removes_row(files: FileRepository) -> None:
    files.add(make_file())

    assert files.delete("f1") is True
    assert files.get("f1") is None


def test_delete_unknown_id_reports_false(files: FileRepository) -> None:
    assert files.delete("ghost") is False


def test_count_tracks_rows(files: FileRepository) -> None:
    assert files.count() == 0

    files.add(make_file("f1"))
    files.add(make_file("f2"))

    assert files.count() == 2


def test_duplicate_content_hash_still_rejected_through_repository(files: FileRepository) -> None:
    files.add(make_file("f1", content_hash="same"))

    with pytest.raises(sqlite3.IntegrityError):
        files.add(make_file("f2", content_hash="same"))


def test_segments_are_listed_in_time_order(
    files: FileRepository, segments: SegmentRepository, db: sqlite3.Connection
) -> None:
    add_video(files, db)
    added = segments.add_many(
        [
            SegmentRecord("s3", "v1", 343.0, 362.0, vector_id=3),
            SegmentRecord("s1", "v1", 135.0, 151.0, vector_id=1),
            SegmentRecord("s2", "v1", 240.0, 255.0, vector_id=2),
        ]
    )

    found = segments.list_for_video("v1")

    assert added == 3
    assert [segment.id for segment in found] == ["s1", "s2", "s3"]
    assert [segment.start_time for segment in found] == [135.0, 240.0, 343.0]


def test_segment_get_round_trips(
    files: FileRepository, segments: SegmentRepository, db: sqlite3.Connection
) -> None:
    add_video(files, db)
    segments.add_many([SegmentRecord("s1", "v1", 0.0, 8.0, 1, "thumbs/s1.jpg")])

    found = segments.get("s1")

    assert found == SegmentRecord("s1", "v1", 0.0, 8.0, 1, "thumbs/s1.jpg")
    assert found.duration == 8.0


def test_segment_get_unknown_returns_none(segments: SegmentRepository) -> None:
    assert segments.get("ghost") is None


def test_segments_for_unknown_video_is_empty(segments: SegmentRepository) -> None:
    assert segments.list_for_video("ghost") == []


def test_segment_lookup_by_vector_ids_preserves_order(
    files: FileRepository, segments: SegmentRepository, db: sqlite3.Connection
) -> None:
    add_video(files, db)
    segments.add_many(
        [
            SegmentRecord("s1", "v1", 0.0, 8.0, vector_id=10),
            SegmentRecord("s2", "v1", 8.0, 20.0, vector_id=20),
        ]
    )

    found = segments.get_by_vector_ids([20, 10])

    assert [segment.id for segment in found] == ["s2", "s1"]


def test_segment_lookup_skips_unknown_vector_ids(
    files: FileRepository, segments: SegmentRepository, db: sqlite3.Connection
) -> None:
    add_video(files, db)
    segments.add_many([SegmentRecord("s1", "v1", 0.0, 8.0, vector_id=10)])

    assert [s.id for s in segments.get_by_vector_ids([10, 999])] == ["s1"]


def test_segment_lookup_with_empty_input(segments: SegmentRepository) -> None:
    assert segments.get_by_vector_ids([]) == []


def test_segment_lookup_spans_variable_limit(
    files: FileRepository, segments: SegmentRepository, db: sqlite3.Connection
) -> None:
    add_video(files, db)
    vector_ids = list(range(1000))
    segments.add_many(
        [SegmentRecord(f"s{n}", "v1", float(n), float(n) + 1.0, vector_id=n) for n in vector_ids]
    )

    assert len(segments.get_by_vector_ids(vector_ids)) == 1000


def test_delete_segments_for_video(
    files: FileRepository, segments: SegmentRepository, db: sqlite3.Connection
) -> None:
    add_video(files, db)
    segments.add_many([SegmentRecord("s1", "v1", 0.0, 8.0), SegmentRecord("s2", "v1", 8.0, 16.0)])

    removed = segments.delete_for_video("v1")

    assert removed == 2
    assert segments.list_for_video("v1") == []


def test_chunks_are_listed_in_document_order(
    files: FileRepository, chunks: ChunkRepository, db: sqlite3.Connection
) -> None:
    add_document(files, db)
    added = chunks.add_many(
        [
            ChunkRecord("c2", "d1", 1, 500, 1000, vector_id=2),
            ChunkRecord("c0", "d1", 0, 0, 500, vector_id=1),
        ]
    )

    found = chunks.list_for_file("d1")

    assert added == 2
    assert [chunk.chunk_index for chunk in found] == [0, 1]
    assert found[0].length == 500


def test_chunk_get_round_trips(
    files: FileRepository, chunks: ChunkRepository, db: sqlite3.Connection
) -> None:
    add_document(files, db)
    chunks.add_many([ChunkRecord("c0", "d1", 0, 0, 42, vector_id=7)])

    assert chunks.get("c0") == ChunkRecord("c0", "d1", 0, 0, 42, vector_id=7)


def test_chunk_get_unknown_returns_none(chunks: ChunkRepository) -> None:
    assert chunks.get("ghost") is None


def test_chunks_for_unknown_file_is_empty(chunks: ChunkRepository) -> None:
    assert chunks.list_for_file("ghost") == []


def test_chunk_lookup_by_vector_ids_preserves_order(
    files: FileRepository, chunks: ChunkRepository, db: sqlite3.Connection
) -> None:
    add_document(files, db)
    chunks.add_many(
        [
            ChunkRecord("c0", "d1", 0, 0, 500, vector_id=11),
            ChunkRecord("c1", "d1", 1, 500, 900, vector_id=22),
        ]
    )

    found = chunks.get_by_vector_ids([22, 11])

    assert [chunk.id for chunk in found] == ["c1", "c0"]


def test_chunk_lookup_skips_unknown_vector_ids(
    files: FileRepository, chunks: ChunkRepository, db: sqlite3.Connection
) -> None:
    add_document(files, db)
    chunks.add_many([ChunkRecord("c0", "d1", 0, 0, 500, vector_id=11)])

    assert [c.id for c in chunks.get_by_vector_ids([11, 999])] == ["c0"]


def test_chunk_lookup_with_empty_input(chunks: ChunkRepository) -> None:
    assert chunks.get_by_vector_ids([]) == []


def test_delete_chunks_for_file(
    files: FileRepository, chunks: ChunkRepository, db: sqlite3.Connection
) -> None:
    add_document(files, db)
    chunks.add_many([ChunkRecord("c0", "d1", 0, 0, 500), ChunkRecord("c1", "d1", 1, 500, 900)])

    removed = chunks.delete_for_file("d1")

    assert removed == 2
    assert chunks.list_for_file("d1") == []


def test_duplicate_chunk_index_is_rejected(
    files: FileRepository, chunks: ChunkRepository, db: sqlite3.Connection
) -> None:
    add_document(files, db)
    chunks.add_many([ChunkRecord("c0", "d1", 0, 0, 500)])

    with pytest.raises(sqlite3.IntegrityError):
        chunks.add_many([ChunkRecord("c1", "d1", 0, 500, 900)])
