from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from fileseek.features.tasks.application.compute import TaskResult, TaskSpec
from fileseek.features.tasks.domain.ports import ProgressReporter
from fileseek.shared.domain.file_types import FileType


class FileHandler(ABC):
    """文件内容计算器。

    每一种文件类型对应一个 Handler，在模型子进程里运行。

    Handler 负责：
        1. 内容抽取
        2. 内容编码
        3. 分类

    Handler 不负责：
        - 写向量库、登记文件块（由服务进程的 `TaskProcessor.persist` 完成）
        - Task 状态管理与持久化
        - 文件生命周期管理

    只读 `TaskSpec`、只返回 `TaskResult`：子进程拿不到服务进程里的 `Task` 实例，改了也
    传不回去；向量库只允许服务进程一个写者（Chroma 不支持多进程并发写）。
    """

    @abstractmethod
    def supports(self, file_type: FileType) -> bool:
        """判断当前 Handler 是否支持指定文件类型。"""
        raise NotImplementedError

    @abstractmethod
    def compute(
        self,
        spec: TaskSpec,
        progress: ProgressReporter,
    ) -> TaskResult:
        """抽取、编码、分类，返回待写入的块、向量和标签。"""
        raise NotImplementedError

    @staticmethod
    def temp_path(spec: TaskSpec) -> Path:
        """任务的本地临时副本路径。"""
        temp_path = spec.metadata.get("temp_path")
        if not isinstance(temp_path, str):
            raise TypeError("任务临时文件路径必须是字符串")
        return Path(temp_path)
