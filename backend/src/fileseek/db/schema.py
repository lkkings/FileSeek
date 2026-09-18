"""Schema definition, expressed as an ordered list of migrations.

Each migration's index in MIGRATIONS is its version number, so the current
schema version is simply the count of applied migrations.
"""

from __future__ import annotations

from dataclasses import dataclass

SCHEMA_VERSION_KEY = "schema_version"

MEDIA_TYPES = ("document", "image", "video")
INDEX_STATES = ("pending", "indexed", "missing", "needs_reindex")
TASK_STATUSES = ("queued", "processing", "completed", "failed")

_META = """
CREATE TABLE IF NOT EXISTS schema_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

_FILES = """
CREATE TABLE files (
    id           TEXT    PRIMARY KEY,
    path         TEXT    NOT NULL UNIQUE,
    filename     TEXT    NOT NULL,
    media_type   TEXT    NOT NULL CHECK (media_type IN ('document', 'image', 'video')),
    size         INTEGER NOT NULL CHECK (size >= 0),
    content_hash TEXT    NOT NULL,
    created_at   INTEGER,
    added_at     INTEGER NOT NULL,
    modified_at  INTEGER,
    index_state  TEXT    NOT NULL DEFAULT 'pending'
                 CHECK (index_state IN ('pending', 'indexed', 'missing', 'needs_reindex'))
);
"""

# Dedup key: a second row with the same content must be rejected by the database
# itself, not only by application-level checks.
_FILES_INDEXES = (
    "CREATE UNIQUE INDEX idx_files_content_hash ON files (content_hash);",
    "CREATE INDEX idx_files_media_type ON files (media_type);",
    "CREATE INDEX idx_files_index_state ON files (index_state);",
    "CREATE INDEX idx_files_added_at ON files (added_at DESC);",
)

# One library file can be submitted from several original locations over time,
# so origins are rows rather than a packed column.
_FILE_ORIGINS = """
CREATE TABLE file_origins (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id       TEXT    NOT NULL REFERENCES files (id) ON DELETE CASCADE,
    original_path TEXT    NOT NULL,
    recorded_at   INTEGER NOT NULL,
    UNIQUE (file_id, original_path)
);
"""

_DOCUMENTS = """
CREATE TABLE documents (
    file_id      TEXT    PRIMARY KEY REFERENCES files (id) ON DELETE CASCADE,
    text_content TEXT,
    page_count   INTEGER,
    language     TEXT,
    chunk_count  INTEGER NOT NULL DEFAULT 0,
    text_source  TEXT    CHECK (text_source IN ('embedded', 'ocr', 'none'))
);
"""

_IMAGES = """
CREATE TABLE images (
    file_id   TEXT    PRIMARY KEY REFERENCES files (id) ON DELETE CASCADE,
    width     INTEGER NOT NULL,
    height    INTEGER NOT NULL,
    ocr_text  TEXT,
    vector_id INTEGER UNIQUE
);
"""

_VIDEOS = """
CREATE TABLE videos (
    file_id        TEXT    PRIMARY KEY REFERENCES files (id) ON DELETE CASCADE,
    duration       REAL    NOT NULL,
    width          INTEGER NOT NULL,
    height         INTEGER NOT NULL,
    fps            REAL,
    sampled_frames INTEGER NOT NULL DEFAULT 0
);
"""

_VIDEO_SEGMENTS = """
CREATE TABLE video_segments (
    id                 TEXT PRIMARY KEY,
    video_id           TEXT NOT NULL REFERENCES videos (file_id) ON DELETE CASCADE,
    start_time         REAL NOT NULL CHECK (start_time >= 0),
    end_time           REAL NOT NULL,
    vector_id          INTEGER UNIQUE,
    thumbnail_rel_path TEXT,
    CHECK (end_time > start_time)
);
"""

_DOC_CHUNKS = """
CREATE TABLE doc_chunks (
    id          TEXT    PRIMARY KEY,
    file_id     TEXT    NOT NULL REFERENCES documents (file_id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL CHECK (chunk_index >= 0),
    char_start  INTEGER NOT NULL CHECK (char_start >= 0),
    char_end    INTEGER NOT NULL,
    vector_id   INTEGER UNIQUE,
    UNIQUE (file_id, chunk_index),
    CHECK (char_end > char_start)
);
"""

# source_path is singular: the spec gives every supported file its own task.
_TASKS = """
CREATE TABLE tasks (
    id               TEXT    PRIMARY KEY,
    source_path      TEXT    NOT NULL,
    media_type       TEXT    CHECK (media_type IN ('document', 'image', 'video')),
    file_id          TEXT    REFERENCES files (id) ON DELETE SET NULL,
    status           TEXT    NOT NULL
                     CHECK (status IN ('queued', 'processing', 'completed', 'failed')),
    stage            TEXT,
    progress         INTEGER NOT NULL DEFAULT 0 CHECK (progress BETWEEN 0 AND 100),
    completed_stages TEXT    NOT NULL DEFAULT '[]',
    error_message    TEXT,
    priority         INTEGER NOT NULL DEFAULT 0,
    created_at       INTEGER NOT NULL,
    started_at       INTEGER,
    completed_at     INTEGER
);
"""

# Matches the queue's claim order: highest priority first, oldest first within it.
_TASKS_INDEXES = (
    "CREATE INDEX idx_tasks_claim ON tasks (status, priority DESC, created_at ASC);",
    "CREATE INDEX idx_tasks_file_id ON tasks (file_id);",
)

_SEGMENT_INDEXES = (
    "CREATE INDEX idx_segments_video_time ON video_segments (video_id, start_time);",
)

_CHUNK_INDEXES = ("CREATE INDEX idx_chunks_file_order ON doc_chunks (file_id, chunk_index);",)

# External-content FTS: the virtual tables hold no copy of the data, they index
# the base rows and are kept in step by triggers.
_FTS_FILENAMES = """
CREATE VIRTUAL TABLE files_fts USING fts5 (
    filename,
    content = 'files',
    content_rowid = 'rowid',
    tokenize = 'unicode61'
);
"""

_FTS_DOCUMENTS = """
CREATE VIRTUAL TABLE documents_fts USING fts5 (
    text_content,
    content = 'documents',
    content_rowid = 'rowid',
    tokenize = 'unicode61'
);
"""

_FTS_TRIGGERS = (
    """
    CREATE TRIGGER files_fts_insert AFTER INSERT ON files BEGIN
        INSERT INTO files_fts (rowid, filename) VALUES (new.rowid, new.filename);
    END;
    """,
    """
    CREATE TRIGGER files_fts_delete AFTER DELETE ON files BEGIN
        INSERT INTO files_fts (files_fts, rowid, filename)
        VALUES ('delete', old.rowid, old.filename);
    END;
    """,
    """
    CREATE TRIGGER files_fts_update AFTER UPDATE OF filename ON files BEGIN
        INSERT INTO files_fts (files_fts, rowid, filename)
        VALUES ('delete', old.rowid, old.filename);
        INSERT INTO files_fts (rowid, filename) VALUES (new.rowid, new.filename);
    END;
    """,
    """
    CREATE TRIGGER documents_fts_insert AFTER INSERT ON documents BEGIN
        INSERT INTO documents_fts (rowid, text_content) VALUES (new.rowid, new.text_content);
    END;
    """,
    """
    CREATE TRIGGER documents_fts_delete AFTER DELETE ON documents BEGIN
        INSERT INTO documents_fts (documents_fts, rowid, text_content)
        VALUES ('delete', old.rowid, old.text_content);
    END;
    """,
    """
    CREATE TRIGGER documents_fts_update AFTER UPDATE OF text_content ON documents BEGIN
        INSERT INTO documents_fts (documents_fts, rowid, text_content)
        VALUES ('delete', old.rowid, old.text_content);
        INSERT INTO documents_fts (rowid, text_content) VALUES (new.rowid, new.text_content);
    END;
    """,
)


_FTS_IMAGES = """
CREATE VIRTUAL TABLE images_fts USING fts5 (
    ocr_text,
    content = 'images',
    content_rowid = 'rowid',
    tokenize = 'unicode61'
);
"""

# Text recognised inside a picture is searchable content too: it is what makes a
# screenshot findable by the words shown in it.
_FTS_IMAGE_TRIGGERS = (
    """
    CREATE TRIGGER images_fts_insert AFTER INSERT ON images BEGIN
        INSERT INTO images_fts (rowid, ocr_text) VALUES (new.rowid, new.ocr_text);
    END;
    """,
    """
    CREATE TRIGGER images_fts_delete AFTER DELETE ON images BEGIN
        INSERT INTO images_fts (images_fts, rowid, ocr_text)
        VALUES ('delete', old.rowid, old.ocr_text);
    END;
    """,
    """
    CREATE TRIGGER images_fts_update AFTER UPDATE OF ocr_text ON images BEGIN
        INSERT INTO images_fts (images_fts, rowid, ocr_text)
        VALUES ('delete', old.rowid, old.ocr_text);
        INSERT INTO images_fts (rowid, ocr_text) VALUES (new.rowid, new.ocr_text);
    END;
    """,
)


@dataclass(frozen=True)
class Migration:
    name: str
    statements: tuple[str, ...]


MIGRATIONS: tuple[Migration, ...] = (
    Migration(
        name="base_tables",
        statements=(
            _FILES,
            *_FILES_INDEXES,
            _FILE_ORIGINS,
            _DOCUMENTS,
            _IMAGES,
            _VIDEOS,
            _VIDEO_SEGMENTS,
            *_SEGMENT_INDEXES,
            _DOC_CHUNKS,
            *_CHUNK_INDEXES,
            _TASKS,
            *_TASKS_INDEXES,
        ),
    ),
    Migration(
        name="full_text_search",
        statements=(_FTS_FILENAMES, _FTS_DOCUMENTS, *_FTS_TRIGGERS),
    ),
    Migration(
        name="image_text_search",
        statements=(_FTS_IMAGES, *_FTS_IMAGE_TRIGGERS),
    ),
)

LATEST_VERSION = len(MIGRATIONS)

META_TABLE_DDL = _META
