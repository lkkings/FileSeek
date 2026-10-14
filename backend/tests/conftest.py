"""全局测试配置。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from fileseek.bootstrap.app import create_app
from fileseek.config.settings import Settings

@pytest.fixture
def app():
    settings = Settings(
        api_prefix="/api/v1",
        database_url="sqlite://:memory:",
        vector_store_path=":memory:",
        environment="test",
        media_stream_chunk_size=1024,
    )
    return create_app(settings=settings, auth_token="test-token")

@pytest.fixture
def client(app):
    return TestClient(app)

@pytest.fixture
def auth_client(client):
    client.headers.update({"X-FileSeek-Token": "test-token"})
    return client
