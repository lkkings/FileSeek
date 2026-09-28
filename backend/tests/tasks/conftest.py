from __future__ import annotations

from pathlib import Path

import pytest
import pytest_asyncio

from fileseek.config.settings import Settings
from fileseek.infrastructure.database import connection


@pytest_asyncio.fixture
async def settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    value = Settings(
        lib_root=tmp_path,
        db_path=tmp_path / "app.db",
        vector_db_path=tmp_path / "vectors",
        embedding_model_cache_dir=tmp_path / "models",
        recycle_dir=tmp_path / "recycle",
        temp_dir=tmp_path / "temp",
    )
    monkeypatch.setattr(connection, "get_settings", lambda: value)
    await connection.init_db()
    yield value
    await connection.close_db()
