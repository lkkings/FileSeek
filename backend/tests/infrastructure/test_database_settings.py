from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from tortoise import Tortoise

from fileseek.config.settings import Settings
from fileseek.infrastructure.database import connection


def _test_settings(root: Path) -> Settings:
    return Settings(
        lib_root=root,
        db_path=root / "app.db",
        vector_db_path=root / "vectors",
        embedding_model_cache_dir=root / "models",
        recycle_dir=root / "recycle",
        temp_dir=root / "temp",
    )


@pytest.mark.asyncio
async def test_init_db_creates_settings_tables(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _test_settings(tmp_path)
    monkeypatch.setattr(connection, "get_settings", lambda: settings)

    try:
        await connection.init_db()
        database = Tortoise.get_connection("default")
        tables = await database.execute_query_dict(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
        table_names = {row["name"] for row in tables}
    finally:
        await connection.close_db()

    assert "storage_locations" in table_names
    assert "classifier_labels" in table_names


@pytest.mark.asyncio
async def test_init_db_seeds_default_classifier_labels(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _test_settings(tmp_path)
    monkeypatch.setattr(connection, "get_settings", lambda: settings)

    try:
        await connection.init_db()
        database = Tortoise.get_connection("default")
        rows = await database.execute_query_dict(
            "SELECT category, label FROM classifier_labels ORDER BY category, label"
        )
    finally:
        await connection.close_db()

    assert rows == [
        {"category": "document", "label": "document"},
        {"category": "image", "label": "image"},
        {"category": "image", "label": "photo"},
        {"category": "video", "label": "video"},
    ]


@pytest.mark.asyncio
async def test_init_db_adds_file_source_columns(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _test_settings(tmp_path)
    database_path = settings.db_path
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database_path) as database:
        database.execute(
            """
            CREATE TABLE files (
                id VARCHAR(64) PRIMARY KEY,
                name VARCHAR(255),
                file_type VARCHAR(32),
                category VARCHAR(32),
                size BIGINT,
                modified TIMESTAMP,
                created_at TIMESTAMP,
                folder_id INT,
                path VARCHAR(4096) UNIQUE
            )
            """
        )
        database.executemany(
            """
            INSERT INTO files (
                id, name, file_type, category, size, modified, created_at, path
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "library-file",
                    "library.txt",
                    "txt",
                    "document",
                    12,
                    "2026-01-01 00:00:00",
                    "2026-01-01 00:00:00",
                    str(tmp_path / "documents" / "library.txt"),
                ),
                (
                    "remote-file",
                    "remote.txt",
                    "txt",
                    "document",
                    12,
                    "2026-01-01 00:00:00",
                    "2026-01-01 00:00:00",
                    "https://example.com/remote.txt",
                ),
            ],
        )
        database.execute(
            """
            INSERT INTO files (
                id, name, file_type, category, size, modified, created_at, path
            )
            VALUES (
                'legacy-file', 'legacy.txt', 'txt', 'document', 12,
                '2026-01-01 00:00:00', '2026-01-01 00:00:00', '/tmp/legacy.txt'
            )
            """
        )

    monkeypatch.setattr(connection, "get_settings", lambda: settings)

    try:
        await connection.init_db()
        database = Tortoise.get_connection("default")
        columns = await database.execute_query_dict("PRAGMA table_info(files)")
        column_names = {row["name"] for row in columns}
        rows = await database.execute_query_dict(
            "SELECT id, storage_id, access_state FROM files ORDER BY id"
        )
    finally:
        await connection.close_db()

    assert {"storage_id", "access_state", "last_checked_at"} <= column_names
    bindings = {row["id"]: row["storage_id"] for row in rows}
    assert bindings == {
        "legacy-file": "local",
        "library-file": "local",
        "remote-file": "external",
    }
    assert all(row["access_state"] == "unknown" for row in rows)
