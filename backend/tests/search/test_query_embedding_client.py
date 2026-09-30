from __future__ import annotations

import os
import time
from pathlib import Path

import numpy as np
import pytest
from tests.search.query_worker_targets import fake_query_worker

from fileseek.config.settings import Settings
from fileseek.features.search.infrastructure.query_worker import (
    QueryEmbeddingClient,
    build_query_worker_config,
    run_query_worker,
)
from fileseek.shared.domain.exceptions import InferenceError
from fileseek.shared.infrastructure.worker import WorkerHandle

MODEL_CACHE = Path.home() / ".cache" / "fileseek" / "models"


def _client(idle_timeout: float = 0, timeout: float = 30.0) -> QueryEmbeddingClient:
    return QueryEmbeddingClient(
        WorkerHandle("test-query-worker", fake_query_worker, {"idle_timeout": idle_timeout}),
        timeout=timeout,
    )


def test_embed_text_runs_in_subprocess() -> None:
    client = _client()
    try:
        assert client.embed_text("hello", query=True) == [[5.0, 1.0]]
        assert client.embed_text(["ab", "abc"]) == [[2.0, 0.0], [3.0, 0.0]]
        assert client.handle.pid not in (None, os.getpid())
    finally:
        client.shutdown()


def test_python_error_raises_inference_error_and_worker_survives() -> None:
    client = _client()
    try:
        with pytest.raises(InferenceError, match="tokenizer broke"):
            client.embed_text("fail")
        assert client.handle.is_alive()
        assert client.embed_text("ok") == [[2.0, 0.0]]
    finally:
        client.shutdown()


def test_crash_raises_then_next_call_restarts() -> None:
    client = _client()
    try:
        client.embed_text("warm")
        first_pid = client.handle.pid

        with pytest.raises(InferenceError, match="SIGKILL"):
            client.embed_text("crash")

        assert client.embed_text("again") == [[5.0, 0.0]]
        assert client.handle.pid != first_pid
    finally:
        client.shutdown()


def test_timeout_terminates_worker_and_next_call_recovers() -> None:
    client = _client(timeout=1.0)
    try:
        started = time.monotonic()
        with pytest.raises(InferenceError, match="超时"):
            client.embed_text("hang")
        assert time.monotonic() - started < 6
        assert not client.handle.is_alive()

        assert client.embed_text("back") == [[4.0, 0.0]]
    finally:
        client.shutdown()


def test_idle_exit_then_query_restarts_transparently() -> None:
    client = _client(idle_timeout=0.3)
    try:
        client.embed_text("first")
        first_pid = client.handle.pid
        time.sleep(1.5)  # 子进程空闲退出

        assert client.embed_text("second") == [[6.0, 0.0]]
        assert client.handle.pid != first_pid
    finally:
        client.shutdown()


def test_warmup_starts_once() -> None:
    client = _client()
    try:
        assert client.ensure_started() is True
        pid = client.handle.pid
        assert client.ensure_started() is False
        assert client.handle.pid == pid
    finally:
        client.shutdown()


@pytest.mark.slow
@pytest.mark.skipif(
    not (MODEL_CACHE / "model_quantized.onnx").exists(),
    reason="需要本地已缓存的 jina-clip-v2 模型",
)
def test_real_query_worker_returns_normalized_1024_vectors(tmp_path: Path) -> None:
    settings = Settings(lib_root=tmp_path, embedding_model_cache_dir=MODEL_CACHE)
    client = QueryEmbeddingClient(
        WorkerHandle(
            "test-real-query-worker", run_query_worker, build_query_worker_config(settings)
        )
    )
    try:
        vectors = np.asarray(client.embed_text("上个月的旅游照片", query=True))
    finally:
        client.shutdown()

    assert vectors.shape == (1, 1024)
    assert np.linalg.norm(vectors[0]) == pytest.approx(1.0, abs=1e-3)
