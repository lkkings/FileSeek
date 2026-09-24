import socket

from fileseek.features.settings.domain.entities import NASConfig
from fileseek.features.settings.domain.exceptions import NASConnectionError
from fileseek.features.settings.domain.repositories import SettingsRepository
from fileseek.features.settings.application.commands import TestNASConnectionCommand
from fileseek.features.settings.application.dto import NASConnectionResultDTO

# 各 NAS 协议的默认连通性测试端口。
# 这里只做“端口可达性”检查，不做完整协议握手（挂载/鉴权留给 NasFileSystemAdapter TODO 实现）。
_PROTOCOL_DEFAULT_PORTS = {
    "smb": 445,
    "nfs": 2049,
    "webdav": 443,
}

_CONNECT_TIMEOUT_SECONDS = 3.0


class TestNASConnectionUseCase:
    def __init__(self, settings_repo: SettingsRepository) -> None:
        self.settings_repo = settings_repo

    def execute(self, command: TestNASConnectionCommand) -> NASConnectionResultDTO:
        """测试 NAS 网络连通性。

        当前仅实现最小可用的“端口可达性”检查（TCP connect），验证网络层面能否触达
        NAS 主机的对应服务端口。完整的协议握手/鉴权/挂载测试依赖 NasFileSystemAdapter
        的 TODO 实现（见 infrastructure/storage/nas_adapter.py），后续接入后应替换为
        真实的凭据校验。

        Args:
            config: NAS 连接配置

        Returns:
            连接成功提示信息

        Raises:
            NASConnectionError: 协议不支持、网络不可达或连接超时
        """
        config = NASConfig(
            protocol=command.protocol,
            host=command.host,
            share_path=command.share_path,
            username=command.username,
            password=command.password,
        )
        port = _PROTOCOL_DEFAULT_PORTS.get(config.protocol)

        if port is None:
            raise NASConnectionError(f"不支持的协议: {config.protocol}")

        try:
            with socket.create_connection((config.host, port), timeout=_CONNECT_TIMEOUT_SECONDS):
                pass
        except OSError as exc:
            raise NASConnectionError(f"无法连接到 {config.host}:{port}: {exc}") from exc

        return NASConnectionResultDTO(message="Connection successful!")
