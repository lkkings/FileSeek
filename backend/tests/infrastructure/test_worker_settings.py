from __future__ import annotations

import pytest
from pydantic import ValidationError

from fileseek.config.settings import Settings


def test_worker_idle_timeouts_have_defaults(tmp_path) -> None:
    settings = Settings(lib_root=tmp_path)

    assert settings.task_worker_idle_timeout == 300.0
    assert settings.query_worker_idle_timeout == 900.0


def test_worker_idle_timeouts_read_from_env(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("TASK_WORKER_IDLE_TIMEOUT", "0")
    monkeypatch.setenv("QUERY_WORKER_IDLE_TIMEOUT", "30")

    settings = Settings(lib_root=tmp_path)

    assert settings.task_worker_idle_timeout == 0
    assert settings.query_worker_idle_timeout == 30


@pytest.mark.parametrize("field", ["task_worker_idle_timeout", "query_worker_idle_timeout"])
def test_worker_idle_timeouts_reject_negative(tmp_path, field: str) -> None:
    with pytest.raises(ValidationError):
        Settings(lib_root=tmp_path, **{field: -1})
