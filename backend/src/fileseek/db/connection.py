"""Connection factory for the local metadata database.

SQLite's locking is unreliable over network filesystems, so a database or index
path that points at a share is rejected outright rather than corrupted later.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from fileseek.db.migrations import migrate
from fileseek.paths import is_network_path

_PRAGMAS = (
    "PRAGMA journal_mode = WAL",
    "PRAGMA synchronous = NORMAL",
    "PRAGMA foreign_keys = ON",
    "PRAGMA busy_timeout = 5000",
)


class LocalPathRequiredError(ValueError):
    """Raised when the database or index is pointed at a network location."""

    def __init__(self, path: Path | str, purpose: str = "database") -> None:
        super().__init__(
            f"{purpose} must live on local disk, refusing network path: {path}. "
            "Only the library itself may sit on a NAS."
        )
        self.path = Path(path)
        self.purpose = purpose


def require_local_path(path: Path | str, purpose: str = "database") -> Path:
    if is_network_path(path):
        raise LocalPathRequiredError(path, purpose)
    return Path(path)


def connect(path: Path | str) -> sqlite3.Connection:
    """Open a connection with FileSeek's pragmas applied.

    `:memory:` is allowed through for tests; every other path must be local.
    """
    if str(path) != ":memory:":
        resolved = require_local_path(path)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        target: Path | str = resolved
    else:
        target = ":memory:"

    connection = sqlite3.connect(target, isolation_level=None)
    connection.row_factory = sqlite3.Row
    for pragma in _PRAGMAS:
        connection.execute(pragma)
    return connection


@contextmanager
def open_database(path: Path | str) -> Iterator[sqlite3.Connection]:
    """Open a migrated database and close it on exit."""
    connection = connect(path)
    try:
        migrate(connection)
        yield connection
    finally:
        connection.close()
