"""模型子进程与服务进程之间的消息协议。

所有消息都是纯数据 dataclass，跨 Pipe 传输时靠 pickle 序列化，所以字段里不能出现
锁、原生句柄或绑定方法——那正是当初线程池没法换成进程池的原因（见 scheduler 模块
docstring）。请求的具体载荷（`TaskSpec`、查询文本）由各自的 feature 定义，这里只约定
子进程回给服务进程的几种消息形状。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProgressMessage:
    """处理进度。`payload` 由具体 worker 约定，导入 worker 用的是 `TaskProgress`。"""

    payload: object


@dataclass(frozen=True)
class ResultMessage:
    """一次请求的最终结果。同一次请求在它之后不会再有任何消息。"""

    payload: object


@dataclass(frozen=True)
class ErrorMessage:
    """子进程内的 Python 异常。进程本身仍然健康，可以继续接下一个请求。

    异常对象本身不回传（未必可 pickle），只带类型名，服务进程据此区分
    "功能尚未实现"这类需要特别对待的错误。
    """

    message: str
    traceback: str = ""
    error_type: str = ""


@dataclass(frozen=True)
class IdleExitMessage:
    """子进程因空闲超时即将正常退出。服务进程据此把它记为"未运行"而不是崩溃。"""


@dataclass(frozen=True)
class ShutdownMessage:
    """服务进程要求子进程收尾退出。"""


WorkerMessage = ProgressMessage | ResultMessage | ErrorMessage | IdleExitMessage | ShutdownMessage
