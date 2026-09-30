"""查询模型子进程。

搜索时的查询向量化放在独立的子进程里，和导入子进程互不共享、互不等待：导入一份要算
十几分钟的大文档时，搜索照常秒回；导入子进程崩溃时，搜索也不受影响，反过来也一样。

子进程空闲一段时间就自己退出（`query_worker_idle_timeout`），把模型内存完整还给系统。
退出后的第一次搜索要等冷启动，所以前端聚焦搜索框时会调预热接口提前把它拉起来。

查询只用得到文本塔，子进程优先加载只含文本塔的子图（见 `JinaClipV2Embedding(text_only=True)`），
比联合模型少占一截内存。
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from multiprocessing.connection import Connection

from fileseek.shared.domain.exceptions import InferenceError
from fileseek.shared.infrastructure.worker import (
    ErrorMessage,
    IdleExitMessage,
    ResultMessage,
    WorkerCrashedError,
    WorkerExitKind,
    WorkerHandle,
    WorkerUnavailableError,
)

logger = logging.getLogger(__name__)

QUERY_WORKER_NAME = "fileseek-query-worker"

# 单次查询的等待上限，包含冷启动加载模型的时间（实测 4~6s）。
QUERY_TIMEOUT_SECONDS = 30.0

# 子进程启动后先跑一次的查询：把 session、tokenizer 都加载起来，JIT 和内存池也完成首次分配。
_WARMUP_QUERY = "warmup"


def build_query_worker_config(settings: object) -> dict[str, object]:
    """从 Settings 取查询子进程需要的字段。"""
    from fileseek.config.settings import Settings
    from fileseek.features.tasks.infrastructure.worker import build_task_worker_config

    assert isinstance(settings, Settings)  # noqa: S101 - 调用方契约
    config = build_task_worker_config(settings)
    config["idle_timeout"] = settings.query_worker_idle_timeout
    return config


def run_query_worker(conn: Connection, config: dict[str, object]) -> None:
    """查询模型子进程入口（spawn 的 target，必须是模块顶层函数）。"""
    from fileseek.config.settings import Settings
    from fileseek.features.tasks.infrastructure.worker import _bootstrap_worker
    from fileseek.infrastructure.embedding import EmbeddingFactory
    from fileseek.shared.infrastructure.worker.loop import serve

    settings = _bootstrap_worker(config)
    assert isinstance(settings, Settings)  # noqa: S101
    embedding = EmbeddingFactory.create(
        provider=settings.embedding_provider,
        model_name=settings.embedding_model_name,
        cache_dir=settings.embedding_model_cache_dir,
        intra_op_num_threads=settings.intra_op_num_threads,
        inter_op_num_threads=settings.inter_op_num_threads,
        text_only=True,
    )
    started = time.monotonic()
    try:
        embedding.embed_text([_WARMUP_QUERY], query=True)
        logger.info("查询模型已就绪（%.1fs）", time.monotonic() - started)
    except Exception:
        # 预热失败不退出：真正的查询会再试一次，失败原因以 ErrorMessage 回给搜索请求。
        logger.exception("查询模型预热失败")

    def handle(request: object, send_progress: Callable[[object], None]) -> object:
        _ = send_progress
        if not isinstance(request, QueryRequest):
            raise TypeError(f"未知请求类型: {type(request).__name__}")
        return embedding.embed_text(list(request.texts), query=request.query)

    idle_timeout = config.get("idle_timeout")
    serve(
        conn,
        handle,
        idle_timeout=float(idle_timeout) if isinstance(idle_timeout, (int, float)) else 0.0,
    )


class QueryRequest:
    """一次查询向量化请求。用普通类而不是 dataclass：pickle 足够，不需要比较。"""

    __slots__ = ("query", "texts")

    def __init__(self, texts: tuple[str, ...], query: bool) -> None:
        self.texts = texts
        self.query = query

    def __getstate__(self) -> tuple[tuple[str, ...], bool]:
        return (self.texts, self.query)

    def __setstate__(self, state: tuple[tuple[str, ...], bool]) -> None:
        self.texts, self.query = state


class QueryEmbeddingClient:
    """服务进程侧的查询向量化（实现 `EmbeddingPort.embed_text`）。

    搜索是交互操作、并发很低，所以同一时刻只放一个请求过去：一把锁把请求串起来，
    省掉请求 id 和结果匹配。超时或子进程崩溃时结束子进程、抛 `InferenceError`，
    下一次调用自动重新拉起。
    """

    def __init__(self, handle: WorkerHandle, *, timeout: float = QUERY_TIMEOUT_SECONDS) -> None:
        self._handle = handle
        self._timeout = timeout
        self._lock = threading.Lock()

    @property
    def handle(self) -> WorkerHandle:
        return self._handle

    def ensure_started(self) -> bool:
        """预热：子进程不在就拉起来（模型在子进程里后台加载），立刻返回。

        Returns:
            这次调用是否真的启动了新进程。冷却期内不启动，返回 False。
        """
        with self._lock:
            self._reap()
            try:
                return self._handle.ensure_started()
            except WorkerUnavailableError as exc:
                logger.warning("查询模型预热跳过: %s", exc)
                return False

    def embed_text(
        self,
        texts: str | list[str],
        *,
        query: bool = False,
    ) -> list[list[float]]:
        batch = (texts,) if isinstance(texts, str) else tuple(texts)
        request = QueryRequest(batch, query)
        with self._lock:
            return self._request(request, retry_idle=True)

    def embed_image(self, images: bytes | list[bytes]) -> list[list[float]]:
        _ = images
        raise NotImplementedError("查询模型进程只提供文本向量化")

    def shutdown(self) -> None:
        with self._lock:
            self._handle.shutdown()

    def _reap(self) -> None:
        """清掉上次已退出（空闲退出或崩溃）的子进程残留状态。"""
        if self._handle.drain_idle_exit():
            return
        self._handle.check_exit()

    def _request(self, request: QueryRequest, *, retry_idle: bool) -> list[list[float]]:
        self._reap()
        try:
            self._handle.ensure_started()
        except WorkerUnavailableError as exc:
            raise InferenceError(f"查询模型暂不可用: {exc}") from exc

        conn = self._handle.conn
        try:
            conn.send(request)
        except (BrokenPipeError, OSError) as exc:
            return self._on_lost(request, retry_idle=retry_idle, cause=exc)

        deadline = time.monotonic() + self._timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                logger.error("查询向量化超时（%.0fs），结束查询模型进程", self._timeout)
                self._handle.terminate()
                raise InferenceError(f"查询向量化超时（{self._timeout:.0f}s）")
            try:
                ready = conn.poll(min(remaining, 0.5))
                if not ready:
                    if not self._handle.is_alive():
                        return self._on_lost(request, retry_idle=retry_idle, cause=None)
                    continue
                message = conn.recv()
            except (EOFError, OSError) as exc:
                return self._on_lost(request, retry_idle=retry_idle, cause=exc)

            if isinstance(message, ResultMessage):
                vectors = message.payload
                if not isinstance(vectors, list):
                    raise InferenceError(f"查询模型返回了未知结果: {type(vectors).__name__}")
                return vectors
            if isinstance(message, ErrorMessage):
                if message.traceback:
                    logger.error("查询向量化失败:\n%s", message.traceback)
                raise InferenceError(f"查询向量化失败: {message.message}")
            if isinstance(message, IdleExitMessage):
                # 请求发出前一刻子进程刚好决定空闲退出：请求没被处理，重新拉起再发一次。
                self._handle.note_idle_exit()
                if retry_idle:
                    return self._request(request, retry_idle=False)
                raise InferenceError("查询模型进程意外退出")

    def _on_lost(
        self,
        request: QueryRequest,
        *,
        retry_idle: bool,
        cause: BaseException | None,
    ) -> list[list[float]]:
        """请求途中子进程没了：空闲退出就重试一次，崩溃就报错（下次调用自动重启）。"""
        exit_info = self._handle.check_exit()
        if exit_info is not None and exit_info.kind is WorkerExitKind.IDLE and retry_idle:
            return self._request(request, retry_idle=False)
        if exit_info is None:
            raise InferenceError("查询模型进程连接中断") from cause
        raise InferenceError(f"查询向量化失败: {WorkerCrashedError(exit_info)}") from cause
