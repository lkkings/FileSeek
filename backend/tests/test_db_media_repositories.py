import sqlite3
from collections.abc import Iterator

import pytest

from fileseek.db import (
    DocumentRecord,
    DocumentRepository,
    FileRecord,
    FileRepository,
    ImageRecord,
    ImageRepository,
    VideoRecord,
    VideoRepository,
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
def images(db: sqlite3.Connection) -> ImageRepository:
    return ImageRepository(db)


@pytest.fixture
def documents(db: sqlite3.Connection) -> DocumentRepository:
    return DocumentRepository(db)


@pytest.fixture
def videos(db: sqlite3.Connection) -> VideoRepository:
    return VideoRepository(db)


def add_file(files: FileRepository, file_id: str, media_type: str = "image") -> str:
    files.add(
        FileRecord(
            id=file_id,
            path=f"/library/{media_type}s/{file_id}",
            filename=file_id,
            media_type=media_type,  # type: ignore[arg-type]
            size=100,
            content_hash=f"hash-{file_id}",
            added_at=1_700_000_000,
        )
    )
    return file_id


def test_image_row_round_trips(files: FileRepository, images: ImageRepository) -> None:
    add_file(files, "cat.jpg")

    images.upsert(ImageRecord("cat.jpg", width=800, height=600, ocr_text="深度学习", vector_id=7))

    stored = images.get("cat.jpg")
    assert stored == ImageRecord("cat.jpg", 800, 600, "深度学习", 7)
    assert stored.has_recognized_text is True


def test_image_without_text_reports_none_recognised(
    files: FileRepository, images: ImageRepository
) -> None:
    add_file(files, "plain.jpg")

    images.upsert(ImageRecord("plain.jpg", width=10, height=10))

    stored = images.get("plain.jpg")
    assert stored is not None
    assert stored.has_recognized_text is False


def test_blank_recognised_text_does_not_count(
    files: FileRepository, images: ImageRepository
) -> None:
    add_file(files, "blank.jpg")

    images.upsert(ImageRecord("blank.jpg", 10, 10, ocr_text="   \n "))

    stored = images.get("blank.jpg")
    assert stored is not None
    assert stored.has_recognized_text is False


def test_reindexing_replaces_the_existing_row(
    files: FileRepository, images: ImageRepository
) -> None:
    """A reindex re-runs for a file that already has a row, so upsert not insert."""
    add_file(files, "cat.jpg")
    images.upsert(ImageRecord("cat.jpg", 800, 600, "old text", 1))

    images.upsert(ImageRecord("cat.jpg", 1024, 768, "new text", 2))

    stored = images.get("cat.jpg")
    assert stored == ImageRecord("cat.jpg", 1024, 768, "new text", 2)


def test_unknown_image_is_none(images: ImageRepository) -> None:
    assert images.get("ghost.jpg") is None


def test_image_lookup_by_vector_preserves_ranking(
    files: FileRepository, images: ImageRepository
) -> None:
    for name, vector_id in (("a.jpg", 10), ("b.jpg", 20), ("c.jpg", 30)):
        add_file(files, name)
        images.upsert(ImageRecord(name, 100, 100, vector_id=vector_id))

    found = images.by_vector_ids([30, 10, 20])

    assert [record.file_id for record in found] == ["c.jpg", "a.jpg", "b.jpg"]


def test_image_lookup_skips_unknown_vectors(files: FileRepository, images: ImageRepository) -> None:
    add_file(files, "a.jpg")
    images.upsert(ImageRecord("a.jpg", 100, 100, vector_id=10))

    assert [r.file_id for r in images.by_vector_ids([10, 999])] == ["a.jpg"]


def test_image_lookup_with_no_vectors(images: ImageRepository) -> None:
    assert images.by_vector_ids([]) == []


def test_vector_ids_for_files_supports_removal(
    files: FileRepository, images: ImageRepository
) -> None:
    """Deleting a file has to take its vectors out of the index too."""
    add_file(files, "a.jpg")
    add_file(files, "b.jpg")
    images.upsert(ImageRecord("a.jpg", 100, 100, vector_id=11))
    images.upsert(ImageRecord("b.jpg", 100, 100, vector_id=22))

    assert sorted(images.vector_ids_for_files(["a.jpg", "b.jpg"])) == [11, 22]


def test_vector_ids_ignores_unindexed_images(
    files: FileRepository, images: ImageRepository
) -> None:
    add_file(files, "pending.jpg")
    images.upsert(ImageRecord("pending.jpg", 100, 100, vector_id=None))

    assert images.vector_ids_for_files(["pending.jpg"]) == []


def test_vector_ids_for_no_files(images: ImageRepository) -> None:
    assert images.vector_ids_for_files([]) == []


def test_deleting_an_image_row(files: FileRepository, images: ImageRepository) -> None:
    add_file(files, "cat.jpg")
    images.upsert(ImageRecord("cat.jpg", 100, 100))

    assert images.delete_for_file("cat.jpg") == 1
    assert images.get("cat.jpg") is None


def test_recognised_text_is_searchable(
    db: sqlite3.Connection, files: FileRepository, images: ImageRepository
) -> None:
    """This is what makes a screenshot findable by the words shown in it."""
    add_file(files, "screenshot.png")
    add_file(files, "other.png")
    images.upsert(ImageRecord("screenshot.png", 100, 100, ocr_text="深度学习 notes"))
    images.upsert(ImageRecord("other.png", 100, 100, ocr_text="grocery list"))

    rows = db.execute(
        "SELECT images.file_id FROM images_fts "
        "JOIN images ON images.rowid = images_fts.rowid WHERE images_fts MATCH ?",
        ("notes",),
    ).fetchall()

    assert [row["file_id"] for row in rows] == ["screenshot.png"]


def test_updated_recognised_text_replaces_the_old_index_entry(
    db: sqlite3.Connection, files: FileRepository, images: ImageRepository
) -> None:
    add_file(files, "shot.png")
    images.upsert(ImageRecord("shot.png", 100, 100, ocr_text="before words"))

    images.upsert(ImageRecord("shot.png", 100, 100, ocr_text="after words"))

    stale = db.execute(
        "SELECT count(*) AS n FROM images_fts WHERE images_fts MATCH ?", ("before",)
    ).fetchone()["n"]
    fresh = db.execute(
        "SELECT count(*) AS n FROM images_fts WHERE images_fts MATCH ?", ("after",)
    ).fetchone()["n"]

    assert (stale, fresh) == (0, 1)


def test_deleted_image_leaves_no_search_entry(
    db: sqlite3.Connection, files: FileRepository, images: ImageRepository
) -> None:
    add_file(files, "shot.png")
    images.upsert(ImageRecord("shot.png", 100, 100, ocr_text="findable text"))

    images.delete_for_file("shot.png")

    hits = db.execute(
        "SELECT count(*) AS n FROM images_fts WHERE images_fts MATCH ?", ("findable",)
    ).fetchone()["n"]
    assert hits == 0


def test_document_row_round_trips(files: FileRepository, documents: DocumentRepository) -> None:
    add_file(files, "paper.pdf", media_type="document")

    documents.upsert(
        DocumentRecord(
            "paper.pdf",
            text_content="a survey of deep learning",
            page_count=12,
            language="en",
            chunk_count=3,
            text_source="embedded",
        )
    )

    stored = documents.get("paper.pdf")
    assert stored is not None
    assert stored.page_count == 12
    assert stored.chunk_count == 3
    assert stored.is_searchable_by_content is True


def test_scan_without_text_is_not_content_searchable(
    files: FileRepository, documents: DocumentRepository
) -> None:
    """A scan whose pages yielded nothing stays findable by name only."""
    add_file(files, "scan.pdf", media_type="document")

    documents.upsert(DocumentRecord("scan.pdf", page_count=4, chunk_count=0, text_source="none"))

    stored = documents.get("scan.pdf")
    assert stored is not None
    assert stored.is_searchable_by_content is False


def test_document_reindex_replaces_the_row(
    files: FileRepository, documents: DocumentRepository
) -> None:
    add_file(files, "paper.pdf", media_type="document")
    documents.upsert(DocumentRecord("paper.pdf", text_content="old", chunk_count=1))

    documents.upsert(DocumentRecord("paper.pdf", text_content="new", chunk_count=5))

    stored = documents.get("paper.pdf")
    assert stored is not None
    assert stored.text_content == "new"
    assert stored.chunk_count == 5


def test_unknown_document_is_none(documents: DocumentRepository) -> None:
    assert documents.get("ghost.pdf") is None


def test_deleting_a_document_row(files: FileRepository, documents: DocumentRepository) -> None:
    add_file(files, "paper.pdf", media_type="document")
    documents.upsert(DocumentRecord("paper.pdf"))

    assert documents.delete_for_file("paper.pdf") == 1
    assert documents.get("paper.pdf") is None


def test_video_row_round_trips(files: FileRepository, videos: VideoRepository) -> None:
    add_file(files, "clip.mp4", media_type="video")

    videos.upsert(
        VideoRecord(
            "clip.mp4", duration=600.0, width=1920, height=1080, fps=25.0, sampled_frames=600
        )
    )

    stored = videos.get("clip.mp4")
    assert stored == VideoRecord("clip.mp4", 600.0, 1920, 1080, 25.0, 600)


def test_video_reindex_replaces_the_row(files: FileRepository, videos: VideoRepository) -> None:
    add_file(files, "clip.mp4", media_type="video")
    videos.upsert(VideoRecord("clip.mp4", 600.0, 1920, 1080, 25.0, 600))

    videos.upsert(VideoRecord("clip.mp4", 600.0, 1920, 1080, 25.0, 1200))

    stored = videos.get("clip.mp4")
    assert stored is not None
    assert stored.sampled_frames == 1200


def test_unknown_video_is_none(videos: VideoRepository) -> None:
    assert videos.get("ghost.mp4") is None


def test_deleting_a_video_row(files: FileRepository, videos: VideoRepository) -> None:
    add_file(files, "clip.mp4", media_type="video")
    videos.upsert(VideoRecord("clip.mp4", 600.0, 1920, 1080))

    assert videos.delete_for_file("clip.mp4") == 1
    assert videos.get("clip.mp4") is None


def test_deleting_the_file_cascades_to_its_media_row(
    files: FileRepository, images: ImageRepository
) -> None:
    add_file(files, "cat.jpg")
    images.upsert(ImageRecord("cat.jpg", 100, 100))

    files.delete("cat.jpg")

    assert images.get("cat.jpg") is None
