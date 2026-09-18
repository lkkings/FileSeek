"""Applies schema migrations and records the resulting version."""

from __future__ import annotations

import sqlite3

from fileseek.db.schema import (
    LATEST_VERSION,
    META_TABLE_DDL,
    MIGRATIONS,
    SCHEMA_VERSION_KEY,
)


class SchemaTooNewError(RuntimeError):
    """The database was written by a newer FileSeek than this one."""

    def __init__(self, found: int, supported: int) -> None:
        super().__init__(
            f"database schema version {found} is newer than supported version {supported}"
        )
        self.found = found
        self.supported = supported


def read_schema_version(connection: sqlite3.Connection) -> int:
    connection.executescript(META_TABLE_DDL)
    row = connection.execute(
        "SELECT value FROM schema_meta WHERE key = ?", (SCHEMA_VERSION_KEY,)
    ).fetchone()
    if row is None:
        return 0
    return int(row[0])


def write_schema_version(connection: sqlite3.Connection, version: int) -> None:
    connection.execute(
        "INSERT INTO schema_meta (key, value) VALUES (?, ?) "
        "ON CONFLICT (key) DO UPDATE SET value = excluded.value",
        (SCHEMA_VERSION_KEY, str(version)),
    )


def migrate(connection: sqlite3.Connection) -> int:
    """Bring the database up to LATEST_VERSION; returns how many migrations ran."""
    current = read_schema_version(connection)
    if current > LATEST_VERSION:
        raise SchemaTooNewError(found=current, supported=LATEST_VERSION)
    if current == LATEST_VERSION:
        return 0

    pending = MIGRATIONS[current:]
    for offset, migration in enumerate(pending, start=current + 1):
        for statement in migration.statements:
            connection.executescript(statement)
        write_schema_version(connection, offset)
    connection.commit()
    return len(pending)
