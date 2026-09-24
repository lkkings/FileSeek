from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any, Literal
from urllib.parse import unquote, urlparse

import smbclient

from fileseek.infrastructure.fs.base import FileSystem
from fileseek.infrastructure.fs.path import VirtualPath


class NasFileSystem(FileSystem):
    """基于 SMB2/SMB3 的 NAS 文件系统。

    VirtualPath 格式：

        smb://server/share/path/to/file.txt

    例如：

        smb://192.168.1.100/data/test.txt

        smb://nas.local/share/documents/a.pdf

    用户名和密码不建议直接写入 URI。

    推荐通过 register_session() 提前注册认证信息：

        fs = NasFileSystem(
            username="admin",
            password="password",
        )

    然后：

        path = VirtualPath(
            "smb://192.168.1.100/data/test.txt"
        )

        path.open("rb")
    """

    def __init__(
        self,
        username: str | None = None,
        password: str | None = None,
        *,
        domain: str | None = None,
        port: int = 445,
        timeout: float = 30,
    ) -> None:

        self.username = username
        self.password = password
        self.domain = domain
        self.port = port
        self.timeout = timeout

        self._sessions: set[tuple[str, str]] = set()

    # ==================================================
    # Session
    # ==================================================

    def _ensure_session(
        self,
        path: VirtualPath,
    ) -> None:
        """确保对应 SMB Server 已建立认证会话。"""

        server, _ = self._parse_path(
            path
        )

        key = (
            server,
            self.username or "",
        )

        if key in self._sessions:
            return

        kwargs: dict[str, Any] = {}

        if self.username is not None:
            kwargs["username"] = self.username

        if self.password is not None:
            kwargs["password"] = self.password

        if self.domain is not None:
            kwargs["auth_protocol"] = "ntlm"

            # smbclient 的用户名可以使用
            # DOMAIN\\username。
            if self.username is not None:
                kwargs["username"] = (
                    f"{self.domain}\\"
                    f"{self.username}"
                )

        smbclient.register_session(
            server,
            port=self.port,
            **kwargs,
        )

        self._sessions.add(
            key
        )

    # ==================================================
    # Open
    # ==================================================

    def open(
        self,
        path: VirtualPath,
        mode: Literal[
            "r",
            "rb",
            "w",
            "wb",
            "a",
            "ab",
            "r+",
            "rb+",
            "w+",
            "wb+",
        ] = "rb",
        **kwargs: Any,
    ):
        """打开 NAS 文件。

        smbclient.open_file() 返回的对象本身就是
        Python 文件对象风格的流，可以直接：

            read()
            write()
            seek()
            tell()
            close()

        """

        self._validate_mode(
            mode
        )

        self._ensure_session(
            path
        )

        remote_path = self._remote_path(
            path
        )

        return smbclient.open_file(
            remote_path,
            mode=mode,
            **kwargs,
        )

    # ==================================================
    # Exists
    # ==================================================

    def exists(
        self,
        path: VirtualPath,
    ) -> bool:
        """判断 NAS 路径是否存在。"""

        try:

            self._ensure_session(
                path
            )

            return smbclient.path.exists(
                self._remote_path(path)
            )

        except OSError:
            return False

    # ==================================================
    # File
    # ==================================================

    def is_file(
        self,
        path: VirtualPath,
    ) -> bool:
        """判断是否为文件。"""

        try:

            self._ensure_session(
                path
            )

            return smbclient.path.isfile(
                self._remote_path(path)
            )

        except OSError:
            return False

    # ==================================================
    # Directory
    # ==================================================

    def is_dir(
        self,
        path: VirtualPath,
    ) -> bool:
        """判断是否为目录。"""

        try:

            self._ensure_session(
                path
            )

            return smbclient.path.isdir(
                self._remote_path(path)
            )

        except OSError:
            return False

    # ==================================================
    # Stat
    # ==================================================

    def stat(
        self,
        path: VirtualPath,
    ):
        """获取 NAS 文件属性。"""

        self._ensure_session(
            path
        )

        return smbclient.stat(
            self._remote_path(path)
        )

    # ==================================================
    # Iterdir
    # ==================================================

    def iterdir(
        self,
        path: VirtualPath,
    ):
        """遍历 NAS 目录。"""

        self._ensure_session(
            path
        )

        remote_path = self._remote_path(
            path
        )

        if not smbclient.path.isdir(
            remote_path
        ):
            raise NotADirectoryError(
                f"不是目录: {path}"
            )

        for entry in smbclient.scandir(
            remote_path
        ):
            yield self._child_path(
                path,
                entry.name,
            )

    # ==================================================
    # Delete
    # ==================================================

    def delete(
        self,
        path: VirtualPath,
    ) -> None:
        """删除 NAS 文件或目录。"""

        self._ensure_session(
            path
        )

        remote_path = self._remote_path(
            path
        )

        if smbclient.path.isdir(
            remote_path
        ):
            smbclient.rmdir(
                remote_path
            )
            return

        smbclient.remove(
            remote_path
        )

    # ==================================================
    # Make Directory
    # ==================================================

    def mkdir(
        self,
        path: VirtualPath,
        *,
        parents: bool = False,
        exist_ok: bool = False,
    ) -> None:
        """创建 NAS 目录。"""

        self._ensure_session(
            path
        )

        remote_path = self._remote_path(
            path
        )

        if exist_ok and smbclient.path.exists(
            remote_path
        ):
            if not smbclient.path.isdir(
                remote_path
            ):
                raise FileExistsError(
                    f"路径已经存在且不是目录: {path}"
                )

            return

        if parents:
            self._mkdir_parents(
                remote_path
            )
        else:
            smbclient.mkdir(
                remote_path
            )

    def _mkdir_parents(
        self,
        path: str,
    ) -> None:
        """递归创建 SMB 目录。"""

        pure = PurePosixPath(
            path.replace(
                "\\",
                "/",
            )
        )

        parts = pure.parts

        if len(parts) < 2:
            return

        current = parts[0]

        for part in parts[1:]:

            current = (
                f"{current}\\{part}"
            )

            if smbclient.path.exists(
                current
            ):
                continue

            smbclient.mkdir(
                current
            )

    # ==================================================
    # Compression
    # ==================================================

    def compress(
        self,
        path: VirtualPath,
        target_path: VirtualPath | None = None,
    ):
        """压缩 NAS 文件。

        NAS FileSystem 不直接实现压缩算法。

        如果未来需要：

            NAS → NAS
            NAS → Local
            NAS → Cloud

        建议由上层 ArchiveService 通过
        FileSystem.open() / write() 完成。

        TODO:
            后续可以实现基于临时文件的流式压缩，
            避免将整个 NAS 文件读取到内存。
        """

        raise NotImplementedError(
            "NasFileSystem 暂不直接提供压缩功能"
        )

    def decompress(
        self,
        path: VirtualPath,
        target_path: VirtualPath | None = None,
    ):
        """解压 NAS 压缩文件。

        TODO:
            后续实现跨 FileSystem 的流式解压：

                NAS → Local
                NAS → NAS
                NAS → Cloud
        """

        raise NotImplementedError(
            "NasFileSystem 暂不直接提供解压功能"
        )

    # ==================================================
    # Path
    # ==================================================

    @staticmethod
    def _parse_path(
        path: VirtualPath,
    ) -> tuple[str, str]:
        """解析 SMB URI。

        smb://server/share/path/file.txt

        返回：

            server
            remote path
        """

        uri = str(path)

        parsed = urlparse(
            uri
        )

        if parsed.scheme.lower() != "smb":
            raise ValueError(
                f"不是 SMB URI: {uri}"
            )

        server = parsed.hostname

        if not server:
            raise ValueError(
                f"SMB URI 缺少服务器地址: {uri}"
            )

        if not parsed.path:
            raise ValueError(
                f"SMB URI 缺少共享目录: {uri}"
            )

        remote_path = unquote(
            parsed.path
        )

        remote_path = remote_path.strip(
            "/"
        )

        if not remote_path:
            raise ValueError(
                f"SMB URI 缺少共享目录: {uri}"
            )

        # SMB 使用反斜杠。
        remote_path = remote_path.replace(
            "/",
            "\\",
        )

        return (
            server,
            remote_path,
        )

    @classmethod
    def _remote_path(
        cls,
        path: VirtualPath,
    ) -> str:
        """把 VirtualPath 转换为 smbclient 路径。"""

        server, remote_path = (
            cls._parse_path(path)
        )

        return (
            f"\\\\{server}"
            f"\\{remote_path}"
        )

    @staticmethod
    def _child_path(
        parent: VirtualPath,
        name: str,
    ) -> VirtualPath:
        """生成子路径。"""

        return VirtualPath(
            str(parent / name)
        )

    # ==================================================
    # Validation
    # ==================================================

    @staticmethod
    def _validate_mode(
        mode: str,
    ) -> None:
        """验证 SMB 文件打开模式。"""

        if not isinstance(
            mode,
            str,
        ):
            raise TypeError(
                "mode 必须是 str"
            )

        valid = {
            "r",
            "rb",
            "w",
            "wb",
            "a",
            "ab",
            "r+",
            "rb+",
            "w+",
            "wb+",
        }

        if mode not in valid:
            raise ValueError(
                f"不支持的文件模式: {mode}"
            )