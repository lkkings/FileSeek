from __future__ import annotations

from pathlib import Path

import pytest
import pytest_asyncio

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


@pytest_asyncio.fixture
async def settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    value = _test_settings(tmp_path)
    monkeypatch.setattr(connection, "get_settings", lambda: value)
    await connection.init_db()
    yield value
    await connection.close_db()
