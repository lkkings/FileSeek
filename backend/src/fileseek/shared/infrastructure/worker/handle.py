"""服务进程侧的模型子进程句柄。

一个 `WorkerHandle` 管一个子进程的整个生命周期：按需启动、判断它是怎么退出的、在连续
崩溃时进入冷却。它不关心子进程具体做什么，请求和结果都是不透明的对象。

为什么用 spawn 而不是 fork：服务进程里已经有 asyncio 事件循环、Tortoise 连接池和
ONNX Runtime 的原生线程，fork 出来的子进程会继承这些状态的一个不一致快照。spawn 起一个
干净的解释器，子进程自己 import、自己构建模型。

退出分三类，处理完全不同（见 `WorkerExitKind`）：
- 空闲退出（exitcode 0）是正常生命周期，下次用到再起，不记错误；
- 被信号杀死（exitcode < 0）几乎总是原生库 abort 或内存耗尽被系统杀掉；
- 非 0 退出码是子进程里没兜住的 Python 层错误。
后两种都算崩溃，计入冷却。
"""

from __future__ import annotations

import contextlib
import logging
import multiprocessing
import signal
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from multiprocessing.connection import Connection
from multiprocessing.process import BaseProcess

from fileseek.shared.infrastructure.worker.protocol import IdleExitMessage, ShutdownMessage

logger = logging.getLogger(__name__)

# 连续崩溃保护：窗口内崩溃达到次数就冷却一段时间，避免同一个坏文件把进程反复拉起。
CRASH_WINDOW_SECONDS = 60.0
CRASH_LIMIT = 3
CRASH_COOLDOWN_SECONDS = 30.0


class WorkerExitKind(str, Enum):
    """子进程的退出方式。"""

    IDLE = "idle"
    SIGNALED = "signaled"
    ERROR_EXIT = "error_exit"
    TERMINATED = "terminated"


@dataclass(frozen=True)
class WorkerExit:
    """一次子进程退出的归类结果。"""

    kind: WorkerExitKind
    exitcode: int | None

    @property
    def is_crash(self) -> bool:
        return self.kind in (WorkerExitKind.SIGNALED, WorkerExitKind.ERROR_EXIT)

    def describe(self) -> str:
        """给任务失败原因、错误日志用的可读描述。"""
        if self.kind is WorkerExitKind.SIGNALED and self.exitcode is not None:
            try:
                name = signal.Signals(-self.exitcode).name
            except ValueError:
                name = str(-self.exitcode)
            return f"处理进程异常退出（signal {name}），可能是内存不足或原生库崩溃"
        if self.kind is WorkerExitKind.ERROR_EXIT:
            return f"处理进程异常退出（exit {self.exitcode}）"
        if self.kind is WorkerExitKind.TERMINATED:
            return "处理进程已被终止"
        return "处理进程已空闲退出"


class WorkerUnavailableError(RuntimeError):
    """子进程处于崩溃冷却期，暂时不接新请求。"""


class WorkerCrashedError(RuntimeError):
    """请求处理期间子进程退出了。"""

    def __init__(self, exit_info: WorkerExit) -> None:
        super().__init__(exit_info.describe())
        self.exit_info = exit_info


WorkerTarget = Callable[[Connection, dict[str, object]], None]


class WorkerHandle:
    """一个按需启动、可替换的模型子进程。

    线程安全：`ensure_started`、`terminate` 和崩溃登记都在内部锁里完成。发送与接收本身
    不加锁——同一时刻只该有一个调用方在和子进程对话，由上层（调度器单任务、查询客户端
    自己的锁）保证。
    """

    def __init__(
        self,
        name: str,
        target: WorkerTarget,
        config: dict[str, object],
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._name = name
        self._target = target
        self._config = config
        self._clock = clock
        self._ctx = multiprocessing.get_context("spawn")
        self._lock = threading.Lock()
        self._process: BaseProcess | None = None
        self._conn: Connection | None = None
        self._crash_times: list[float] = []
        self._cooldown_until = 0.0
        # 由 terminate() 主动结束的进程不算崩溃，靠这个标记区分。
        self._terminating = False

    @property
    def name(self) -> str:
        return self._name

    @property
    def conn(self) -> Connection:
        if self._conn is None:
            raise RuntimeError(f"{self._name} 尚未启动")
        return self._conn

    @property
    def pid(self) -> int | None:
        return None if self._process is None else self._process.pid

    def is_alive(self) -> bool:
        return self._process is not None and self._process.is_alive()

    def in_cooldown(self) -> bool:
        return self._clock() < self._cooldown_until

    def ensure_started(self) -> bool:
        """子进程不在就启动它。返回这次调用是否真的启动了新进程。

        Raises:
            WorkerUnavailableError: 处于连续崩溃后的冷却期。
        """
        with self._lock:
            if self.is_alive():
                return False
            if self.in_cooldown():
                remaining = self._cooldown_until - self._clock()
                raise WorkerUnavailableError(
                    f"{self._name} 连续崩溃，冷却中（还剩 {remaining:.0f}s）"
                )
            self._discard_locked()
            parent_conn, child_conn = self._ctx.Pipe(duplex=True)
            process = self._ctx.Process(
                target=self._target,
                args=(child_conn, self._config),
                name=self._name,
                # 服务进程异常退出时子进程跟着走，不留孤儿进程占着几个 GB 内存。
                daemon=True,
            )
            process.start()
            # 子进程已经持有自己那一端，父进程这边关掉，否则子进程退出后父进程读不到 EOF。
            child_conn.close()
            self._process = process
            self._conn = parent_conn
            self._terminating = False
            logger.info("%s 已启动 (pid=%s)", self._name, process.pid)
            return True

    def check_exit(self) -> WorkerExit | None:
        """子进程已退出时返回归类结果并登记（崩溃计入冷却），仍在运行返回 None。

        同一次退出只会被归类、登记一次：之后再调用返回 None，直到下一个进程启动。
        """
        with self._lock:
            process = self._process
            if process is None or process.is_alive():
                return None
            process.join(timeout=0)
            exit_info = self._classify(process.exitcode)
            self._discard_locked()
            if exit_info.is_crash:
                self._record_crash_locked()
                logger.error("%s %s", self._name, exit_info.describe())
            else:
                logger.info("%s 已退出（%s）", self._name, exit_info.kind.value)
            return exit_info

    def note_idle_exit(self) -> None:
        """收到子进程的 `IdleExitMessage` 后调用：等它退干净，不记为崩溃。"""
        with self._lock:
            process = self._process
        if process is not None:
            process.join(timeout=2.0)
        self.check_exit()

    def terminate(self, grace: float = 3.0) -> WorkerExit | None:
        """主动结束子进程：先 SIGTERM，宽限期后仍在就 SIGKILL。不计入崩溃。"""
        with self._lock:
            process = self._process
            if process is None:
                return None
            self._terminating = True
        if process.is_alive():
            process.terminate()
            process.join(timeout=grace)
            if process.is_alive():
                logger.warning("%s 在 %.1fs 内未响应 SIGTERM，强制结束", self._name, grace)
                process.kill()
                process.join(timeout=grace)
        return self.check_exit()

    def shutdown(self, grace: float = 2.0) -> None:
        """请求子进程收尾退出，超时就强制结束。服务关闭时调用。"""
        with self._lock:
            process = self._process
            conn = self._conn
            if process is None:
                return
            self._terminating = True
        if process.is_alive() and conn is not None:
            with contextlib.suppress(OSError, ValueError):
                conn.send(ShutdownMessage())
            process.join(timeout=grace)
        self.terminate(grace=grace)

    def drain_idle_exit(self) -> bool:
        """非阻塞检查管道里是否只剩一条 `IdleExitMessage`；是则按空闲退出收尾。

        用于请求发出前的竞态检测：子进程可能恰好在我们发请求前一刻决定空闲退出。
        """
        conn = self._conn
        if conn is None:
            return False
        try:
            while conn.poll(0):
                message = conn.recv()
                if isinstance(message, IdleExitMessage):
                    self.note_idle_exit()
                    return True
        except (EOFError, OSError):
            return False
        return False

    def _classify(self, exitcode: int | None) -> WorkerExit:
        if self._terminating:
            return WorkerExit(WorkerExitKind.TERMINATED, exitcode)
        if exitcode == 0:
            return WorkerExit(WorkerExitKind.IDLE, exitcode)
        if exitcode is not None and exitcode < 0:
            return WorkerExit(WorkerExitKind.SIGNALED, exitcode)
        return WorkerExit(WorkerExitKind.ERROR_EXIT, exitcode)

    def _record_crash_locked(self) -> None:
        now = self._clock()
        self._crash_times = [t for t in self._crash_times if now - t < CRASH_WINDOW_SECONDS]
        self._crash_times.append(now)
        if len(self._crash_times) >= CRASH_LIMIT:
            self._cooldown_until = now + CRASH_COOLDOWN_SECONDS
            self._crash_times.clear()
            logger.error(
                "%s 在 %.0fs 内崩溃 %d 次，冷却 %.0fs",
                self._name,
                CRASH_WINDOW_SECONDS,
                CRASH_LIMIT,
                CRASH_COOLDOWN_SECONDS,
            )

    def _discard_locked(self) -> None:
        if self._conn is not None:
            with contextlib.suppress(OSError):
                self._conn.close()
        self._conn = None
        self._process = None
