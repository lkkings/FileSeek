import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from fileseek.db import (
    LATEST_VERSION,
    LocalPathRequiredError,
    SchemaTooNewError,
    connect,
    migrate,
    open_database,
    read_schema_version,
)
from fileseek.db.connection import require_local_path
from fileseek.db.migrations import write_schema_version
from fileseek.db.schema import MIGRATIONS

EXPECTED_TABLES = {
    "schema_meta",
    "files",
    "file_origins",
    "documents",
    "images",
    "videos",
    "video_segments",
    "doc_chunks",
    "tasks",
}

EXPECTED_COLUMNS = {
    "files": {
        "id",
        "path",
        "filename",
        "media_type",
        "size",
        "content_hash",
        "created_at",
        "added_at",
        "modified_at",
        "index_state",
    },
    "file_origins": {"id", "file_id", "original_path", "recorded_at"},
    "documents": {
        "file_id",
        "text_content",
        "page_count",
        "language",
        "chunk_count",
        "text_source",
    },
    "images": {"file_id", "width", "height", "ocr_text", "vector_id"},
    "videos": {"file_id", "duration", "width", "height", "fps", "sampled_frames"},
    "video_segments": {
        "id",
        "video_id",
        "start_time",
        "end_time",
        "vector_id",
        "thumbnail_rel_path",
    },
    "doc_chunks": {"id", "file_id", "chunk_index", "char_start", "char_end", "vector_id"},
    "tasks": {
        "id",
        "source_path",
        "media_type",
        "file_id",
        "status",
        "stage",
        "progress",
        "completed_stages",
        "error_message",
        "priority",
        "created_at",
        "started_at",
        "completed_at",
    },
}


@pytest.fixture
def db() -> Iterator[sqlite3.Connection]:
    connection = connect(":memory:")
    migrate(connection)
    yield connection
    connection.close()


def table_names(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return {row["name"] for row in rows}


def column_names(connection: sqlite3.Connection, table: str) -> set[str]:
    rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
    return {row["name"] for row in rows}


def insert_file(
    connection: sqlite3.Connection,
    file_id: str = "f1",
    *,
    path: str = "/library/images/a.jpg",
    filename: str = "a.jpg",
    media_type: str = "image",
    content_hash: str = "hash-a",
) -> None:
    connection.execute(
        "INSERT INTO files (id, path, filename, media_type, size, content_hash, added_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (file_id, path, filename, media_type, 10, content_hash, 1_700_000_000),
    )


def test_migration_creates_expected_tables(db: sqlite3.Connection) -> None:
    assert table_names(db) >= EXPECTED_TABLES


@pytest.mark.parametrize("table", sorted(EXPECTED_COLUMNS))
def test_tables_have_expected_columns(db: sqlite3.Connection, table: str) -> None:
    assert column_names(db, table) == EXPECTED_COLUMNS[table]


def test_migration_creates_expected_indexes(db: sqlite3.Connection) -> None:
    rows = db.execute("SELECT name FROM sqlite_master WHERE type = 'index'").fetchall()
    names = {row["name"] for row in rows}

    assert {
        "idx_files_content_hash",
        "idx_files_media_type",
        "idx_files_index_state",
        "idx_files_added_at",
        "idx_segments_video_time",
        "idx_chunks_file_order",
        "idx_tasks_claim",
        "idx_tasks_file_id",
    } <= names


def test_fresh_migration_reports_latest_version(db: sqlite3.Connection) -> None:
    assert read_schema_version(db) == LATEST_VERSION


def test_migrate_applies_every_migration_once() -> None:
    connection = connect(":memory:")
    applied = migrate(connection)

    assert applied == LATEST_VERSION
    connection.close()


def test_migrate_is_a_no_op_when_version_matches(db: sqlite3.Connection) -> None:
    assert migrate(db) == 0
    assert read_schema_version(db) == LATEST_VERSION


def test_migrate_upgrades_from_older_version() -> None:
    connection = connect(":memory:")
    read_schema_version(connection)
    for statement in MIGRATIONS[0].statements:
        connection.executescript(statement)
    write_schema_version(connection, 1)

    applied = migrate(connection)

    assert applied == LATEST_VERSION - 1
    assert read_schema_version(connection) == LATEST_VERSION
    assert "documents_fts" in table_names(connection)
    connection.close()


def test_migrate_refuses_newer_schema() -> None:
    connection = connect(":memory:")
    read_schema_version(connection)
    write_schema_version(connection, LATEST_VERSION + 5)

    with pytest.raises(SchemaTooNewError) as excinfo:
        migrate(connection)

    assert excinfo.value.found == LATEST_VERSION + 5
    assert excinfo.value.supported == LATEST_VERSION
    connection.close()


def test_duplicate_content_hash_is_rejected(db: sqlite3.Connection) -> None:
    insert_file(db, "f1", path="/library/images/a.jpg", content_hash="same")

    with pytest.raises(sqlite3.IntegrityError, match="content_hash"):
        insert_file(db, "f2", path="/library/images/b.jpg", content_hash="same")


def test_same_name_different_content_both_survive(db: sqlite3.Connection) -> None:
    insert_file(db, "f1", path="/library/images/a.jpg", filename="a.jpg", content_hash="h1")
    insert_file(db, "f2", path="/library/images/a-2.jpg", filename="a.jpg", content_hash="h2")

    count = db.execute("SELECT count(*) AS n FROM files WHERE filename = 'a.jpg'").fetchone()["n"]
    assert count == 2


def test_media_type_is_constrained(db: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        insert_file(db, "f1", media_type="spreadsheet")


def test_index_state_is_constrained(db: sqlite3.Connection) -> None:
    insert_file(db)

    with pytest.raises(sqlite3.IntegrityError):
        db.execute("UPDATE files SET index_state = 'unknown' WHERE id = 'f1'")


def test_segment_time_range_is_constrained(db: sqlite3.Connection) -> None:
    insert_file(db, "v1", path="/library/videos/v.mp4", filename="v.mp4", media_type="video")
    db.execute(
        "INSERT INTO videos (file_id, duration, width, height, fps) VALUES (?, ?, ?, ?, ?)",
        ("v1", 60.0, 1920, 1080, 25.0),
    )

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO video_segments (id, video_id, start_time, end_time) VALUES (?, ?, ?, ?)",
            ("s1", "v1", 10.0, 10.0),
        )


def test_foreign_keys_cascade_on_file_delete(db: sqlite3.Connection) -> None:
    insert_file(db, "v1", path="/library/videos/v.mp4", filename="v.mp4", media_type="video")
    db.execute(
        "INSERT INTO videos (file_id, duration, width, height, fps) VALUES (?, ?, ?, ?, ?)",
        ("v1", 60.0, 1920, 1080, 25.0),
    )
    db.execute(
        "INSERT INTO video_segments (id, video_id, start_time, end_time) VALUES (?, ?, ?, ?)",
        ("s1", "v1", 0.0, 8.0),
    )

    db.execute("DELETE FROM files WHERE id = 'v1'")

    assert db.execute("SELECT count(*) AS n FROM videos").fetchone()["n"] == 0
    assert db.execute("SELECT count(*) AS n FROM video_segments").fetchone()["n"] == 0


def test_filename_fts_finds_matching_file(db: sqlite3.Connection) -> None:
    insert_file(
        db,
        "f1",
        path="/library/documents/deep.pdf",
        filename="deep-learning.pdf",
        media_type="document",
        content_hash="h1",
    )
    insert_file(
        db,
        "f2",
        path="/library/documents/other.pdf",
        filename="tax-return.pdf",
        media_type="document",
        content_hash="h2",
    )

    rows = db.execute(
        "SELECT f.id FROM files_fts JOIN files f ON f.rowid = files_fts.rowid "
        "WHERE files_fts MATCH ?",
        ("learning",),
    ).fetchall()

    assert [row["id"] for row in rows] == ["f1"]


def test_document_text_fts_finds_matching_document(db: sqlite3.Connection) -> None:
    insert_file(
        db,
        "f1",
        path="/library/documents/a.pdf",
        filename="a.pdf",
        media_type="document",
        content_hash="h1",
    )
    db.execute(
        "INSERT INTO documents (file_id, text_content, page_count) VALUES (?, ?, ?)",
        ("f1", "a survey of transformer architectures", 12),
    )

    rows = db.execute(
        "SELECT d.file_id FROM documents_fts JOIN documents d ON d.rowid = documents_fts.rowid "
        "WHERE documents_fts MATCH ?",
        ("transformer",),
    ).fetchall()

    assert [row["file_id"] for row in rows] == ["f1"]


def test_document_fts_reflects_updates(db: sqlite3.Connection) -> None:
    insert_file(
        db,
        "f1",
        path="/library/documents/a.pdf",
        filename="a.pdf",
        media_type="document",
        content_hash="h1",
    )
    db.execute("INSERT INTO documents (file_id, text_content) VALUES (?, ?)", ("f1", "before text"))
    db.execute("UPDATE documents SET text_content = ? WHERE file_id = ?", ("after words", "f1"))

    stale = db.execute(
        "SELECT count(*) AS n FROM documents_fts WHERE documents_fts MATCH ?", ("before",)
    ).fetchone()["n"]
    fresh = db.execute(
        "SELECT count(*) AS n FROM documents_fts WHERE documents_fts MATCH ?", ("after",)
    ).fetchone()["n"]

    assert (stale, fresh) == (0, 1)


def test_fts_drops_deleted_rows(db: sqlite3.Connection) -> None:
    insert_file(db, "f1", filename="kitten.jpg")
    db.execute("DELETE FROM files WHERE id = 'f1'")

    hits = db.execute(
        "SELECT count(*) AS n FROM files_fts WHERE files_fts MATCH ?", ("kitten",)
    ).fetchone()["n"]

    assert hits == 0


def test_filename_fts_matches_unicode_terms(db: sqlite3.Connection) -> None:
    insert_file(db, "f1", filename="深度学习 notes.pdf", media_type="document")

    hits = db.execute(
        "SELECT count(*) AS n FROM files_fts WHERE files_fts MATCH ?", ("notes",)
    ).fetchone()["n"]

    assert hits == 1


@pytest.mark.parametrize(
    "candidate",
    [r"\\nas\share\metadata.db", "//nas/share/metadata.db", "smb://nas/library/metadata.db"],
)
def test_network_database_path_is_rejected(candidate: str) -> None:
    with pytest.raises(LocalPathRequiredError, match="local disk"):
        connect(candidate)


def test_require_local_path_reports_purpose() -> None:
    with pytest.raises(LocalPathRequiredError) as excinfo:
        require_local_path("//nas/share/index", purpose="vector index")

    assert excinfo.value.purpose == "vector index"
    assert "vector index" in str(excinfo.value)


def test_require_local_path_returns_local_path(tmp_path: Path) -> None:
    assert require_local_path(tmp_path / "metadata.db") == tmp_path / "metadata.db"


def test_connect_creates_parent_directory(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "deeper" / "metadata.db"

    connection = connect(target)
    connection.close()

    assert target.parent.is_dir()


def test_connect_enables_foreign_keys_and_wal(tmp_path: Path) -> None:
    connection = connect(tmp_path / "metadata.db")

    assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert connection.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    connection.close()


def test_open_database_migrates_and_closes(tmp_path: Path) -> None:
    with open_database(tmp_path / "metadata.db") as connection:
        assert read_schema_version(connection) == LATEST_VERSION

    with pytest.raises(sqlite3.ProgrammingError):
        connection.execute("SELECT 1")


def test_schema_survives_reopen(tmp_path: Path) -> None:
    target = tmp_path / "metadata.db"
    with open_database(target) as connection:
        insert_file(connection, "f1")

    with open_database(target) as connection:
        assert connection.execute("SELECT count(*) AS n FROM files").fetchone()["n"] == 1
        assert migrate(connection) == 0
