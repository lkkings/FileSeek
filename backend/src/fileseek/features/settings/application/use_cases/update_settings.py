from pathlib import Path

from fileseek.features.settings.domain.entities import Settings
from fileseek.features.settings.domain.exceptions import InvalidPathError
from fileseek.features.settings.domain.repositories import SettingsRepository
from fileseek.features.settings.application.commands import UpdateSettingsCommand
from fileseek.features.settings.application.dto import SettingsDTO
from fileseek.features.settings.application.mappers import settings_to_dto


class UpdateSettingsUseCase:
    def __init__(self, settings_repo: SettingsRepository) -> None:
        self.settings_repo = settings_repo

    async def execute(self, command: UpdateSettingsCommand) -> SettingsDTO:
        """更新存储根路径。

        Args:
            lib_root: 新的存储根路径

        Raises:
            InvalidPathError: 路径不存在、不是目录或不可写
        """
        lib_root = command.lib_root
        path = Path(lib_root)

        if not path.exists():
            try:
                path.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                raise InvalidPathError(f"路径不可创建: {lib_root}") from exc

        if not path.is_dir():
            raise InvalidPathError(f"路径不是目录: {lib_root}")

        if not _is_writable(path):
            raise InvalidPathError(f"路径不可写: {lib_root}")

        current = await self.settings_repo.get_settings()
        updated = Settings(lib_root=str(path), nas_enabled=current.nas_enabled)
        await self.settings_repo.save_settings(updated)

        return settings_to_dto(updated)


def _is_writable(path: Path) -> bool:
    """检查目录是否可写。"""
    probe = path / ".fileseek_write_test"
    try:
        probe.touch(exist_ok=True)
        probe.unlink()
    except OSError:
        return False
    return True
