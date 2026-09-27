from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from fileseek.features.library.domain.exceptions import FolderNotEmptyError
from fileseek.shared.domain.file_types import FileType,FileCategory


@dataclass
class Folder:
    id: str
    name: str
    icon_type: str
    description: str
    modified: datetime
    file_count: int = 0

    def rename(self, name: str) -> None:
        if not name.strip():
            raise ValueError("文件夹名称不能为空")
        self.name = name
        self._touch()

    def change_icon_type(self, icon_type: str) -> None:
        self.icon_type = icon_type
        self._touch()

    def change_description(self, description: str) -> None:
        self.description = description
        self._touch()

    def ensure_can_delete(self) -> None:
        if self.file_count > 0:
            raise FolderNotEmptyError("文件夹非空，无法直接删除。请先清空或转移其中的文件。")

    def increase_file_count(self) -> None:
        self.file_count += 1
        self._touch()

    def decrease_file_count(self) -> None:
        if self.file_count <= 0:
            raise ValueError("文件数量不能小于 0")
        self.file_count -= 1
        self._touch()

    def _touch(self) -> None:
        self.modified = datetime.now(UTC).isoformat()

@dataclass
class File:
    """文件领域实体。"""
    id: str
    name: str
    file_type: FileType
    category: FileCategory
    size: int
    modified: datetime
    path: str
    folder_id: str | None = None
    tags: list[str] = field(default_factory=list)
    chunks: list[FileChunk] = field(default_factory=list)

    def move_to_folder(self, folder_id: str | None) -> None:
        """将文件移动到指定文件夹。

        Args:
            folder_id: 目标文件夹 ID，None 表示移动到根目录
        """
        self.folder_id = folder_id

    def add_tags(self,tags:list[str]) -> None:
        self.tags.extend(tags)

    def add_chunks(self,chunks: list[FileChunk]) -> None:
        self.chunks.extend(chunks)

@dataclass
class FileChunk:
    id: str
    file_id: str
    score: float = 0
    metadata: dict[str, object] | None = None

    def set_score(self,score: float):
        self.score = score

__all__ = ["File", "Folder"]
