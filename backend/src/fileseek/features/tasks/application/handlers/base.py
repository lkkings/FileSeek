from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


from fileseek.features.library.domain.entities import FileChunk
from fileseek.features.tasks.domain.ports import ProgressReporter
from fileseek.features.tasks.domain.entities import Task
from fileseek.shared.domain.file_types import FileType


class FileHandler(ABC):
    """文件内容处理器。

    每一种文件类型对应一个 Handler。

    Handler 负责：
        1. 内容抽取
        2. 内容编码
        3. 分类

    Handler 不负责：
        - Task 状态管理
        - Task 持久化
        - 任务进度持久化
        - 文件生命周期管理
    """

    @abstractmethod
    def supports(self, file_type: FileType) -> bool:
        """判断当前 Handler 是否支持指定文件类型。"""
        raise NotImplementedError


    @abstractmethod
    def process(
        self,
        task: Task,
        progress: ProgressReporter,
    ) -> None:
        """处理文件并返回分类标签。"""
        raise NotImplementedError