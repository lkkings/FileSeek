from __future__ import annotations

import pickle
import time

import numpy as np
import pytest
from tests.infrastructure.worker_targets import echo_worker

from fileseek.shared.infrastructure.worker import (
    ErrorMessage,
    IdleExitMessage,
    ProgressMessage,
    ResultMessage,
    ShutdownMessage,
    WorkerExitKind,
    WorkerHandle,
    WorkerUnavailableError,
)
from fileseek.shared.infrastructure.worker import handle as handle_module


def _recv_until_result(worker: WorkerHandle, timeout: float = 20.0) -> list[object]:
    messages: list[object] = []
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if worker.conn.poll(0.05):
            message = worker.conn.recv()
            messages.append(message)
            if isinstance(message, (ResultMessage, ErrorMessage, IdleExitMessage)):
                return messages
    raise AssertionError(f"超时未收到结果: {messages}")


def _wait_exit(worker: WorkerHandle, timeout: float = 20.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        exit_info = worker.check_exit()
        if exit_info is not None:
            return exit_info
        time.sleep(0.05)
    raise AssertionError("子进程未退出")


@pytest.mark.parametrize(
    "message",
    [
        ProgressMessage(("stage", 1, 2)),
        ResultMessage({"vectors": np.ones((2, 3), dtype=np.float32)}),
        ErrorMessage("bad", "Traceback ..."),
        IdleExitMessage(),
        ShutdownMessage(),
    ],
)
def test_messages_survive_pickle_round_trip(message) -> None:
    restored = pickle.loads(pickle.dumps(message))  # noqa: S301 - 自己刚序列化的数据

    assert type(restored) is type(message)
    if isinstance(message, ResultMessage):
        np.testing.assert_array_equal(restored.payload["vectors"], message.payload["vectors"])
    else:
        assert restored == message


def test_worker_echoes_request_with_progress() -> None:
    worker = WorkerHandle("test-worker", echo_worker, {"idle_timeout": 0})
    try:
        assert worker.ensure_started() is True
        assert worker.ensure_started() is False

        worker.conn.send("hello")
        messages = _recv_until_result(worker)

        assert messages == [
            ProgressMessage(("progress", "hello")),
            ResultMessage(("echo", "hello")),
        ]
    finally:
        worker.terminate()


def test_python_exception_is_returned_and_worker_keeps_serving() -> None:
    worker = WorkerHandle("test-worker", echo_worker, {"idle_timeout": 0})
    try:
        worker.ensure_started()
        worker.conn.send("raise")
        error = _recv_until_result(worker)[-1]
        assert isinstance(error, ErrorMessage)
        assert error.message == "boom"

        worker.conn.send("again")
        assert _recv_until_result(worker)[-1] == ResultMessage(("echo", "again"))
        assert worker.is_alive()
    finally:
        worker.terminate()


@pytest.mark.parametrize(
    ("request_", "kind", "fragment"),
    [
        ("sigkill", WorkerExitKind.SIGNALED, "SIGKILL"),
        ("abort", WorkerExitKind.SIGNALED, "SIGABRT"),
        ("exit3", WorkerExitKind.ERROR_EXIT, "exit 3"),
    ],
)
def test_crash_is_classified(request_: str, kind: WorkerExitKind, fragment: str) -> None:
    worker = WorkerHandle("test-worker", echo_worker, {"idle_timeout": 0})
    worker.ensure_started()
    worker.conn.send(request_)

    exit_info = _wait_exit(worker)

    assert exit_info.kind is kind
    assert exit_info.is_crash
    assert fragment in exit_info.describe()
    # 同一次退出只登记一次
    assert worker.check_exit() is None


def test_idle_timeout_exits_cleanly_and_restarts_on_demand(caplog) -> None:
    worker = WorkerHandle("test-worker", echo_worker, {"idle_timeout": 0.2})
    worker.ensure_started()

    messages = _recv_until_result(worker)
    assert messages == [IdleExitMessage()]
    worker.note_idle_exit()

    assert worker.is_alive() is False
    assert not [r for r in caplog.records if r.levelname == "ERROR"]

    # 空闲退出后下一次请求照常成功
    try:
        assert worker.ensure_started() is True
        worker.conn.send("after-idle")
        assert _recv_until_result(worker)[-1] == ResultMessage(("echo", "after-idle"))
    finally:
        worker.terminate()


def test_drain_idle_exit_detects_race() -> None:
    worker = WorkerHandle("test-worker", echo_worker, {"idle_timeout": 0.2})
    worker.ensure_started()
    time.sleep(1.5)  # 让子进程已经发出 IdleExitMessage

    assert worker.drain_idle_exit() is True
    assert worker.is_alive() is False


def test_terminate_is_not_counted_as_crash() -> None:
    worker = WorkerHandle("test-worker", echo_worker, {"idle_timeout": 0})
    worker.ensure_started()
    worker.conn.send(("sleep", 30))
    time.sleep(0.5)

    started = time.monotonic()
    exit_info = worker.terminate(grace=3.0)

    assert time.monotonic() - started < 5
    assert exit_info is not None
    assert exit_info.kind is WorkerExitKind.TERMINATED
    assert not exit_info.is_crash


def test_repeated_crashes_trigger_cooldown(monkeypatch) -> None:
    now = [1000.0]
    worker = WorkerHandle("test-worker", echo_worker, {"idle_timeout": 0}, clock=lambda: now[0])

    for _ in range(handle_module.CRASH_LIMIT):
        worker.ensure_started()
        worker.conn.send("sigkill")
        assert _wait_exit(worker).is_crash
        now[0] += 1

    with pytest.raises(WorkerUnavailableError):
        worker.ensure_started()

    now[0] += handle_module.CRASH_COOLDOWN_SECONDS
    try:
        assert worker.ensure_started() is True
    finally:
        worker.terminate()


def test_crashes_outside_window_do_not_trigger_cooldown() -> None:
    now = [1000.0]
    worker = WorkerHandle("test-worker", echo_worker, {"idle_timeout": 0}, clock=lambda: now[0])

    for _ in range(handle_module.CRASH_LIMIT):
        worker.ensure_started()
        worker.conn.send("sigkill")
        assert _wait_exit(worker).is_crash
        now[0] += handle_module.CRASH_WINDOW_SECONDS

    try:
        assert worker.ensure_started() is True
    finally:
        worker.terminate()
