"""`python -m fileseek` 命令行的用例。

`uvicorn.run` 一律被打桩：真跑起来会占端口、阻塞测试。这里验的是它被调用时拿到的
参数对不对——host/port/日志配置一错，桌面端要么连不上，要么日志丢一半。
"""

from __future__ import annotations

import socket
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from fileseek.config.settings import Settings
from fileseek.main import find_free_port, main


@pytest.fixture
def captured_uvicorn(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """拦住 uvicorn.run，记录它收到的参数。"""
    captured: dict[str, Any] = {}

    def fake_run(app: object, **kwargs: Any) -> None:
        captured["app"] = app
        captured.update(kwargs)

    monkeypatch.setattr("fileseek.main.uvicorn.run", fake_run)
    return captured


@pytest.fixture
def cli_env(
    monkeypatch: pytest.MonkeyPatch,
    test_settings: Settings,
    isolated_config_dir: Path,
) -> Settings:
    """让 CLI 拿到临时配置，别碰真机的库和配置目录。"""
    monkeypatch.setattr("fileseek.main.get_settings", lambda: test_settings)
    return test_settings


def test_find_free_port_prefers_requested_port() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        free = probe.getsockname()[1]

    # 上面的 socket 已关闭，这个端口应当还能拿到。
    assert find_free_port("127.0.0.1", free) == free


def test_find_free_port_falls_back_when_taken() -> None:
    """端口被占时换一个，而不是启动失败。

    固定端口在"上一次的进程还没退干净"时每次都失败，这是开发时最常见的情形。
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as holder:
        holder.bind(("127.0.0.1", 0))
        holder.listen(1)
        taken = holder.getsockname()[1]

        chosen = find_free_port("127.0.0.1", taken)

        assert chosen != taken
        assert chosen > 0


def test_cli_runs_server_on_requested_port(
    cli_env: Settings, captured_uvicorn: dict[str, Any]
) -> None:
    result = CliRunner().invoke(main, ["--port", "8791"])

    assert result.exit_code == 0
    assert captured_uvicorn["port"] == 8791
    assert captured_uvicorn["host"] == "127.0.0.1"


def test_cli_defaults_to_loopback(
    cli_env: Settings, captured_uvicorn: dict[str, Any]
) -> None:
    """默认只监听 127.0.0.1：文件库是用户的私有文件，没理由暴露到网络上。"""
    CliRunner().invoke(main, [])

    assert captured_uvicorn["host"] == "127.0.0.1"


def test_cli_passes_app_with_publishing_enabled(
    cli_env: Settings, captured_uvicorn: dict[str, Any]
) -> None:
    """自己 bind 端口的进程必须发布连接文件，否则桌面端永远等不到就绪。"""
    CliRunner().invoke(main, ["--port", "8792"])

    app = captured_uvicorn["app"]
    assert app.state.publish_connection is True
    assert app.state.port == 8792
    assert app.state.auth_token


def test_cli_keeps_own_log_config(
    cli_env: Settings, captured_uvicorn: dict[str, Any]
) -> None:
    """log_config=None：日志已配好（stderr + 文件），交给 uvicorn 重配会顶掉文件那一路。

    stderr 那一路不是冗余——桌面端启动失败时读的就是子进程 stderr 的尾部。
    """
    CliRunner().invoke(main, ["--log-level", "DEBUG"])

    assert captured_uvicorn["log_config"] is None
    assert captured_uvicorn["log_level"] == "debug"


def test_cli_rejects_unknown_log_level(cli_env: Settings) -> None:
    result = CliRunner().invoke(main, ["--log-level", "TRACE"])

    assert result.exit_code != 0


def test_cli_creates_config_directory(
    cli_env: Settings, captured_uvicorn: dict[str, Any], isolated_config_dir: Path
) -> None:
    """日志要落到配置目录，所以目录得先建出来。"""
    CliRunner().invoke(main, ["--port", "8793"])

    assert isolated_config_dir.is_dir()


def test_cli_help_lists_options(cli_env: Settings) -> None:
    result = CliRunner().invoke(main, ["--help"])

    assert result.exit_code == 0
    for flag in ("--host", "--port", "--log-level"):
        assert flag in result.output
