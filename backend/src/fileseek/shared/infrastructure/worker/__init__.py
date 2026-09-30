"""模型子进程的通用基础设施：消息协议与进程句柄。"""

from fileseek.shared.infrastructure.worker.handle import (
    WorkerCrashedError,
    WorkerExit,
    WorkerExitKind,
    WorkerHandle,
    WorkerUnavailableError,
)
from fileseek.shared.infrastructure.worker.protocol import (
    ErrorMessage,
    IdleExitMessage,
    ProgressMessage,
    ResultMessage,
    ShutdownMessage,
    WorkerMessage,
)

__all__ = [
    "ErrorMessage",
    "IdleExitMessage",
    "ProgressMessage",
    "ResultMessage",
    "ShutdownMessage",
    "WorkerCrashedError",
    "WorkerExit",
    "WorkerExitKind",
    "WorkerHandle",
    "WorkerMessage",
    "WorkerUnavailableError",
]
