from __future__ import annotations

from fileseek.shared.domain.file_types import FileType

from fileseek.features.tasks.application.handlers.base import FileHandler


class FileHandlerRegistry:
    """文件 Handler 注册表。

    根据 FileType 找到对应的 Handler。
    """

    def __init__(
        self,
        handlers: list[FileHandler],
    ) -> None:
        self._handlers = tuple(handlers)

    def get(
        self,
        file_type: FileType,
    ) -> FileHandler:
        """获取指定文件类型对应的 Handler。"""
        matched = [
            handler
            for handler in self._handlers
            if handler.supports(file_type)
        ]

        if not matched:
            raise ValueError(
                f"没有找到对应的文件 Handler: "
                f"{file_type}"
            )

        if len(matched) > 1:
            raise RuntimeError(
                f"存在多个文件 Handler 支持 "
                f"{file_type}: {matched}"
            )
        return matched[0]