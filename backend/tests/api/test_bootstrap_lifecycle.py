"""装配、连接文件、生命周期的用例。

连接文件是和桌面端的硬约定（Rust 侧 `sidecar.rs` / `connection.rs`）：位置按平台算、
内容是 `{port, token}`、写入必须原子、关闭时要撤掉。这几条错一个，桌面端就连不上或者
一直连着一个没人监听的端口，所以单独验。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from fileseek.bootstrap import connection
from fileseek.bootstrap.app import PORT_ENV_VAR, create_app, create_service_app
from fileseek.config.paths import AppPaths
from fileseek.config.settings import Settings


def test_generated_tokens_are_unique_per_call() -> None:
    """token 每次启动重新生成，上次泄露的不会一直有效。"""
    assert connection.generate_token() != connection.generate_token()


def test_publish_writes_port_and_token(tmp_path: Path) -> None:
    target = tmp_path / "connection.json"

    connection.publish(target, 8765, "tok")

    # 形状是 Rust 侧 ConnectionInfo 反序列化的目标，多一层嵌套就读不出来。
    assert json.loads(target.read_text()) == {"port": 8765, "token": "tok"}


def test_publish_creates_parent_directory(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "deeper" / "connection.json"

    connection.publish(target, 1, "tok")

    assert target.is_file()


@pytest.mark.skipif(sys.platform == "win32", reason="Windows 不用 POSIX 权限位")
def test_publish_restricts_permissions(tmp_path: Path) -> None:
    """token 是凭据，只给文件属主读写。"""
    target = tmp_path / "connection.json"

    connection.publish(target, 1, "tok")

    assert target.stat().st_mode & 0o777 == 0o600


def test_publish_leaves_no_temp_file(tmp_path: Path) -> None:
    """原子写用的临时文件不能留下来。"""
    target = tmp_path / "connection.json"

    connection.publish(target, 1, "tok")

    assert [p.name for p in tmp_path.iterdir()] == ["connection.json"]


def test_publish_overwrites_previous_run(tmp_path: Path) -> None:
    target = tmp_path / "connection.json"
    connection.publish(target, 1, "old")

    connection.publish(target, 2, "new")

    assert json.loads(target.read_text()) == {"port": 2, "token": "new"}


def test_revoke_removes_file(tmp_path: Path) -> None:
    target = tmp_path / "connection.json"
    connection.publish(target, 1, "tok")

    connection.revoke(target)

    assert not target.exists()


def test_revoke_is_silent_when_file_is_absent(tmp_path: Path) -> None:
    """关闭路径不能因为文件已经没了就抛异常——那会盖掉真正的退出原因。"""
    connection.revoke(tmp_path / "never-existed.json")


def test_app_paths_match_desktop_convention() -> None:
    """路径规则必须和 Rust 侧 `sidecar::connection_file_path` 一致。"""
    paths = AppPaths.resolve()

    assert paths.connection_file.name == "connection.json"
    if sys.platform == "darwin":
        assert paths.config_dir.parts[-3:] == ("Library", "Application Support", "FileSeek")
    elif sys.platform == "win32":
        assert paths.config_dir.name == "FileSeek"
    else:
        assert paths.config_dir.name == "fileseek"


def test_lifespan_publishes_then_revokes_connection_file(
    test_settings: Settings, isolated_config_dir: Path
) -> None:
    """连接文件在服务运行期间存在，关闭后消失。

    这就是桌面端的就绪信号：它先等这个文件被重写，再打 /health。
    """
    app = create_app(port=8899, publish_connection=True, settings=test_settings)
    connection_file = isolated_config_dir / "connection.json"

    with TestClient(app):
        assert connection_file.is_file()
        assert json.loads(connection_file.read_text())["port"] == 8899

    assert not connection_file.exists()


def test_lifespan_skips_publishing_when_not_asked(
    test_settings: Settings, isolated_config_dir: Path
) -> None:
    """只有真正在监听端口的进程才该发布，否则会把桌面端指到一个死端口。"""
    app = create_app(port=8899, publish_connection=False, settings=test_settings)

    with TestClient(app):
        assert not (isolated_config_dir / "connection.json").exists()


def test_lifespan_creates_library_directories(
    test_settings: Settings, isolated_config_dir: Path
) -> None:
    app = create_app(publish_connection=False, settings=test_settings)

    with TestClient(app):
        root = test_settings.lib_root
        assert (root / "documents").is_dir()
        assert (root / "images").is_dir()
        assert (root / "videos").is_dir()
        assert (root / ".recycle").is_dir()


def test_lifespan_initialises_database(
    test_settings: Settings, isolated_config_dir: Path
) -> None:
    """建表是启动的一部分：连接文件在它之后才发布，所以第一个请求不会打在空库上。"""
    app = create_app(publish_connection=False, settings=test_settings)

    with TestClient(app):
        assert test_settings.db_path is not None
        assert test_settings.db_path.is_file()


def test_create_app_uses_configured_api_prefix(
    test_settings: Settings, isolated_config_dir: Path
) -> None:
    app = create_app(publish_connection=False, settings=test_settings)

    paths = app.openapi()["paths"]

    assert "/api/v1/library/folders" in paths
    # /health 不带前缀：桌面端按固定路径打它。
    assert "/health" in paths


def test_service_app_reads_port_from_env(
    monkeypatch: pytest.MonkeyPatch, test_settings: Settings, isolated_config_dir: Path
) -> None:
    """uvicorn --factory 模式下端口只能靠环境变量告知。"""
    monkeypatch.setenv(PORT_ENV_VAR, "8123")

    app = create_service_app()

    assert app.state.port == 8123
    assert app.state.publish_connection is True


def test_service_app_without_port_does_not_publish(
    monkeypatch: pytest.MonkeyPatch, test_settings: Settings, isolated_config_dir: Path
) -> None:
    """没设 FILESEEK_PORT 就不发布：写一个错端口比不写更糟。"""
    monkeypatch.delenv(PORT_ENV_VAR, raising=False)

    app = create_service_app()

    assert app.state.port is None
    assert app.state.publish_connection is False
