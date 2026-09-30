"""导入模型子进程。

子进程入口 `run_task_worker` 自己构建 parser、embedding、OCR、classifier——这些对象持有
锁和原生句柄，不可 pickle，也不该从服务进程传过来。服务进程侧用 `TaskWorkerClient`
把 `TaskSpec` 发过去、把进度和结果收回来。

临时文件在子进程里处理完就删：它是给计算用的副本，写入阶段不再需要。子进程崩溃时来不及
删，那份副本由服务进程在判定崩溃后兜底删除。
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from multiprocessing.connection import Connection
from pathlib import Path
from typing import TYPE_CHECKING

from fileseek.features.tasks.application.compute import (
    TaskComputeFailedError,
    TaskResult,
    TaskSpec,
)
from fileseek.shared.infrastructure.worker import (
    ErrorMessage,
    IdleExitMessage,
    ProgressMessage,
    ResultMessage,
    WorkerCrashedError,
    WorkerExitKind,
    WorkerHandle,
)

if TYPE_CHECKING:
    from fileseek.features.tasks.application.handlers import FileHandlerRegistry

logger = logging.getLogger(__name__)

TASK_WORKER_NAME = "fileseek-task-worker"


def build_task_worker_config(settings: object) -> dict[str, object]:
    """从 Settings 取子进程需要的字段。

    只传纯数据，不传 Settings 对象本身：子进程用 `Settings(**config)` 重建，避免它重新
    读一遍环境变量和 .env，和服务进程拿到不同的配置。
    """
    from fileseek.config.settings import Settings

    assert isinstance(settings, Settings)  # noqa: S101 - 调用方契约
    return {
        "settings": settings.model_dump(mode="python"),
        "idle_timeout": settings.task_worker_idle_timeout,
        "log_file": _log_file(),
        "log_level": logging.getLevelName(logging.getLogger().level),
    }


def _log_file() -> str | None:
    for handler in logging.getLogger().handlers:
        filename = getattr(handler, "baseFilename", None)
        if filename:
            return str(filename)
    return None


def _bootstrap_worker(config: dict[str, object]) -> object:
    """子进程启动时的公共准备：日志、配置单例。返回重建的 Settings。"""
    from fileseek.bootstrap.logging_config import configure_logging
    from fileseek.config import settings as settings_module

    log_file = config.get("log_file")
    configure_logging(
        level=str(config.get("log_level") or "INFO"),
        log_file=Path(str(log_file)) if log_file else None,
        worker=True,
    )
    settings_data = config.get("settings")
    if isinstance(settings_data, dict):
        rebuilt = settings_module.Settings(**settings_data)
        # 工厂函数里的 get_settings() 带 lru_cache，替换成服务进程传来的那份配置。
        settings_module.get_settings.cache_clear()
        settings_module.get_settings = lambda: rebuilt  # type: ignore[assignment]
        return rebuilt
    return settings_module.get_settings()


def build_handler_registry(settings: object) -> FileHandlerRegistry:
    """在子进程里组装文件 handler。

    handler 的依赖（parser、embedding、OCR）在函数里才 import：服务进程 import 本模块
    只为拿 `TaskWorkerClient`，不该因此把模型栈拉进来。
    """
    from fileseek.config.settings import Settings
    from fileseek.features.tasks.application.handlers import (
        DocumentHandler,
        FileHandlerRegistry,
        ImageHandler,
        VideoHandler,
    )
    from fileseek.features.tasks.infrastructure.file_processor.document_parser import (
        DocumentParser,
    )
    from fileseek.features.tasks.infrastructure.file_processor.video_sampler import (
        VideoSampler,
    )
    from fileseek.infrastructure.classifier.factory import SnapshotClassifierProvider
    from fileseek.infrastructure.embedding import get_embedding_service
    from fileseek.infrastructure.ocr import get_ocr_service

    assert isinstance(settings, Settings)  # noqa: S101
    embedding_service = get_embedding_service()
    classifier_provider = SnapshotClassifierProvider()
    return FileHandlerRegistry(
        handlers=[
            DocumentHandler(
                document_parser=DocumentParser(
                    chunk_size=settings.document_chunk_size,
                    overlap=settings.document_overlap,
                ),
                embedding_service=embedding_service,
                classifier=classifier_provider,
                batch_size=settings.task_document_batch_size,
            ),
            ImageHandler(
                ocr_service=get_ocr_service(),
                embedding_service=embedding_service,
                classifier=classifier_provider,
            ),
            VideoHandler(
                video_sampler=VideoSampler(
                    sample_every_n_frames=settings.video_sample_every_n_frames,
                    hash_threshold=settings.video_perceptual_hash_threshold,
                ),
                embedding_service=embedding_service,
                classifier=classifier_provider,
                batch_size=settings.task_video_batch_size,
            ),
        ]
    )


def make_task_request_handler(
    registry: FileHandlerRegistry,
) -> Callable[[object, Callable[[object], None]], object]:
    """把 handler 注册表包成 worker 主循环要的请求处理函数。"""
    from fileseek.features.tasks.application.progress_reporter import (
        CallbackProgressReporter,
    )

    def handle(request: object, send_progress: Callable[[object], None]) -> object:
        if not isinstance(request, TaskSpec):
            raise TypeError(f"未知请求类型: {type(request).__name__}")
        logger.info("开始计算任务: task_id=%s, path=%s", request.task_id, request.file_path)
        handler = registry.get(request.file_type)
        progress = CallbackProgressReporter(send_progress)
        try:
            result = handler.compute(request, progress)
        finally:
            remove_temp_file(request)
        logger.info("任务计算完成: task_id=%s, chunks=%d", request.task_id, len(result.chunks))
        return result

    return handle


def run_task_worker(conn: Connection, config: dict[str, object]) -> None:
    """导入模型子进程入口（spawn 的 target，必须是模块顶层函数）。"""
    from fileseek.shared.infrastructure.worker.loop import serve

    settings = _bootstrap_worker(config)
    registry = build_handler_registry(settings)
    serve(
        conn,
        make_task_request_handler(registry),
        idle_timeout=_as_float(config.get("idle_timeout")),
    )


def _as_float(value: object) -> float:
    return float(value) if isinstance(value, (int, float, str)) else 0.0


def remove_temp_file(spec: TaskSpec) -> None:
    temp_path = spec.metadata.get("temp_path")
    if isinstance(temp_path, str):
        Path(temp_path).unlink(missing_ok=True)


class TaskWorkerClient:
    """服务进程侧的导入计算进程（实现 `TaskComputePort`）。

    一次只处理一个任务：`submit` 之后反复 `poll`，直到拿到 `TaskResult` 或一个异常实例。
    """

    def __init__(self, handle: WorkerHandle) -> None:
        self._handle = handle
        self._spec: TaskSpec | None = None

    @property
    def handle(self) -> WorkerHandle:
        return self._handle

    def in_cooldown(self) -> bool:
        return self._handle.in_cooldown()

    def submit(self, spec: TaskSpec) -> None:
        """把任务交给子进程；子进程不在就先拉起。

        发送前先看一眼管道：子进程可能恰好刚决定空闲退出，这种情况重新拉起再发，
        只重试这一次。
        """
        self._handle.ensure_started()
        if self._handle.drain_idle_exit():
            self._handle.ensure_started()
        self._spec = spec
        try:
            self._handle.conn.send(spec)
        except (BrokenPipeError, OSError):
            # 发送那一刻子进程已经走了：若是空闲退出就重来一次，否则交给 poll 按崩溃处理。
            exit_info = self._handle.check_exit()
            if exit_info is None or exit_info.kind is WorkerExitKind.IDLE:
                self._handle.ensure_started()
                self._handle.conn.send(spec)

    def poll(self) -> object | None:
        """非阻塞取下一个事件：`TaskProgress`、`TaskResult` 或异常实例；暂无事件返回 None。"""
        spec = self._spec
        if spec is None:
            return None
        try:
            conn = self._handle.conn
            if conn.poll(0):
                message = conn.recv()
                return self._translate(message)
        except (EOFError, OSError, RuntimeError):
            pass

        exit_info = self._handle.check_exit()
        if exit_info is None:
            return None
        # 结果没回来进程就退了：无论哪种退出，这个任务都没有结果了。
        self._spec = None
        remove_temp_file(spec)
        return WorkerCrashedError(exit_info)

    def terminate(self) -> None:
        spec = self._spec
        self._spec = None
        self._handle.terminate()
        if spec is not None:
            remove_temp_file(spec)

    def shutdown(self) -> None:
        self._spec = None
        self._handle.shutdown()

    def _translate(self, message: object) -> object | None:
        if isinstance(message, ProgressMessage):
            return message.payload
        if isinstance(message, ResultMessage):
            self._spec = None
            payload = message.payload
            if not isinstance(payload, TaskResult):
                return TaskComputeFailedError(f"子进程返回了未知结果: {type(payload).__name__}")
            return payload
        if isinstance(message, ErrorMessage):
            self._spec = None
            if message.traceback:
                logger.error("子进程计算失败:\n%s", message.traceback)
            return TaskComputeFailedError(message.message, message.error_type)
        if isinstance(message, IdleExitMessage):
            # 有在飞任务时不会空闲退出；真遇到了说明请求没送达，按空闲退出收尾，
            # 下一轮 poll 会看到进程已退出并报告。
            self._handle.note_idle_exit()
            return None
        return None
