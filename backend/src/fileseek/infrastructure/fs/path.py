from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from fileseek.infrastructure.fs.register import FileSystemRegistry


class VirtualPath:
    """统一表示本地路径和远程 URI 的虚拟路径。

    支持：

        /tmp/test.txt
        ./test.txt
        C:/test.txt
        C:\\test.txt
        file:///tmp/test.txt
        file:///C:/test.txt
        http://example.com/test.txt
        https://example.com/test.txt

    VirtualPath 本身只负责路径语义和 URI 解析，
    实际文件系统操作由对应的 FileSystem 实现负责。
    """

    def __init__(self, uri: str):
        if isinstance(uri,Path):
            uri = str(uri)
        if not isinstance(uri, str):
            raise TypeError(
                f"uri 必须是 str，实际类型为 {type(uri).__name__}"
            )

        if not uri:
            raise ValueError("uri 不能为空")

        (
            self.uri,
            self.scheme,
            self.host,
            self.path,
        ) = self._parse(uri)

        self.fs = FileSystemRegistry.get(
            self.scheme
        )

    # ==================================================
    # Parse
    # ==================================================

    @classmethod
    def _parse(
        cls,
        value: str,
    ) -> tuple[str, str, str, str]:

        # ----------------------------------------------
        # 1. Windows 本地路径
        # ----------------------------------------------

        if cls._is_windows_path(value):

            path = Path(value)

            return (
                path.as_uri(),
                "file",
                "",
                str(path),
            )

        # ----------------------------------------------
        # 2. Unix 本地路径
        # ----------------------------------------------

        path = Path(value)

        if path.is_absolute():

            return (
                path.as_uri(),
                "file",
                "",
                str(path),
            )

        # ----------------------------------------------
        # 3. URI
        # ----------------------------------------------

        parsed = urlparse(value)

        scheme = parsed.scheme.lower()

        # 没有 scheme 的相对路径
        if not scheme:

            path = path.resolve()

            return (
                path.as_uri(),
                "file",
                "",
                str(path),
            )

        # ----------------------------------------------
        # 4. file:// URI
        # ----------------------------------------------

        if scheme == "file":

            path = cls._file_uri_to_path(
                parsed
            )

            uri = cls._build_uri(
                scheme="file",
                host=parsed.netloc,
                path=path,
            )

            return (
                uri,
                scheme,
                parsed.netloc,
                path,
            )

        # ----------------------------------------------
        # 5. 远程 URI
        # ----------------------------------------------

        uri = urlunparse(
            (
                scheme,
                parsed.netloc,
                parsed.path,
                parsed.params,
                parsed.query,
                parsed.fragment,
            )
        )

        return (
            uri,
            scheme,
            parsed.netloc,
            parsed.path or "/",
        )

    @staticmethod
    def _is_windows_path(
        value: str,
    ) -> bool:

        # C:\xxx
        if len(value) >= 3:
            if (
                value[1] == ":"
                and value[2] in ("\\", "/")
            ):
                return True

        # \\server\share\xxx
        if value.startswith("\\\\"):
            return True

        return False

    @staticmethod
    def _file_uri_to_path(parsed) -> str:

        path = parsed.path

        # Windows:
        #
        # file:///C:/test.txt
        #
        if (
            os.name == "nt"
            and len(path) >= 3
            and path[0] == "/"
            and path[2] == ":"
        ):
            path = path[1:]

        return path

    @staticmethod
    def _build_uri(
        scheme: str,
        host: str,
        path: str,
    ) -> str:

        if scheme == "file":

            if os.name == "nt":

                normalized = path.replace(
                    "\\",
                    "/",
                )

                if not normalized.startswith("/"):
                    normalized = "/" + normalized

                return (
                    f"file://{host}"
                    f"{normalized}"
                )

            return (
                f"file://{host}"
                f"{path}"
            )

        return (
            f"{scheme}://"
            f"{host}"
            f"{path}"
        )

    def is_local(self):
        return self.scheme == "file"

    # ==================================================
    # File System
    # ==================================================

    def open(
        self,
        mode: str = "rb",
        **kwargs,
    ):
        return self.fs.open(
            self,
            mode=mode,
            **kwargs,
        )

    def delete(self):
        return self.fs.delete(self)

    def read_bytes(self) -> bytes:
        with self.fs.open(
            self,
            "rb"
        ) as f:
            return f.read()

    def exists(self) -> bool:

        return self.fs.exists(
            self
        )

    def is_file(self) -> bool:

        return self.fs.is_file(
            self
        )

    def is_dir(self) -> bool:

        return self.fs.is_dir(
            self
        )

    def stat(self):

        return self.fs.stat(
            self
        )

    def iterdir(self):

        return self.fs.iterdir(
            self
        )

    # ==================================================
    # Path Operations
    # ==================================================

    def joinpath(
        self,
        *parts: str,
    ) -> VirtualPath:

        if not parts:
            return self

        current = self

        for part in parts:

            if not isinstance(part, str):
                raise TypeError(
                    "路径组件必须是 str"
                )

            if not part:
                continue

            # URI 路径不应该直接使用 os.path.join，
            # 因为远程路径始终使用 POSIX 风格。
            path = (
                current.path.rstrip("/")
                + "/"
                + part.lstrip("/")
            )

            current = VirtualPath(
                self._build_uri(
                    scheme=current.scheme,
                    host=current.host,
                    path=path,
                )
            )

        return current

    def __truediv__(
        self,
        child: str,
    ) -> VirtualPath:

        return self.joinpath(
            child
        )

    # ==================================================
    # Properties
    # ==================================================

    @property
    def name(self) -> str:

        path = self.path.rstrip("/")

        if not path:
            return ""

        return path.rsplit(
            "/",
            1,
        )[-1]

    @property
    def suffix(self) -> str:

        return Path(self.name).suffix

    @property
    def stem(self) -> str:

        return Path(self.name).stem

    @property
    def parent(self) -> VirtualPath:

        path = self.path.rstrip("/")

        if not path:
            return self

        parent = path.rsplit(
            "/",
            1,
        )[0]

        if not parent:
            parent = "/"

        return VirtualPath(
            self._build_uri(
                scheme=self.scheme,
                host=self.host,
                path=parent,
            )
        )

    # ==================================================
    # Compression
    # ==================================================

    def compress(
        self,
        target_path: str | VirtualPath,
    ):

        target = self._ensure_virtual_path(
            target_path
        )

        return self.fs.compress(
            self,
            target,
        )

    def decompress(
        self,
        target_path: str | VirtualPath,
    ):

        target = self._ensure_virtual_path(
            target_path
        )

        return self.fs.decompress(
            self,
            target,
        )

    @staticmethod
    def _ensure_virtual_path(
        value: str | VirtualPath,
    ) -> VirtualPath:

        if isinstance(value, VirtualPath):
            return value

        if isinstance(value, str):
            return VirtualPath(value)

        if isinstance(value, Path):
            return VirtualPath(str(value))


        raise TypeError(
            "target_path 必须是 str 或 VirtualPath"
        )

    # ==================================================
    # Python Protocol
    # ==================================================

    def __str__(self) -> str:

        return self.uri

    def __repr__(self) -> str:

        return (
            f"VirtualPath("
            f"{self.uri!r}"
            f")"
        )

    def __eq__(
        self,
        other,
    ) -> bool:

        if not isinstance(
            other,
            VirtualPath,
        ):
            return NotImplemented

        return self.uri == other.uri

    def __hash__(self) -> int:

        return hash(
            self.uri
        )