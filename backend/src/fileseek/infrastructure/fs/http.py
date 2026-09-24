from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import requests

from fileseek.infrastructure.fs.base import FileSystem
from fileseek.infrastructure.fs.path import VirtualPath


class HttpStream:
    """HTTP 顺序只读流。

    特性：

    - 只支持顺序读取
    - 不支持 seek
    - 不支持 write
    - 支持 read(size)
    - 支持 read()
    - 支持上下文管理器
    - 支持逐块读取
    """

    DEFAULT_CHUNK_SIZE = 8192

    def __init__(
        self,
        response: requests.Response,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
    ) -> None:

        if chunk_size <= 0:
            raise ValueError(
                "chunk_size 必须大于 0"
            )

        self.response = response

        self.chunk_size = chunk_size

        self.iterator: Iterator[bytes] = (
            response.iter_content(
                chunk_size=chunk_size
            )
        )

        self._buffer = bytearray()

        self._eof = False
        self._closed = False

    # ==================================================
    # Read
    # ==================================================

    def read(
        self,
        size: int = -1,
    ) -> bytes:
        """读取数据。

        Args:
            size:
                -1：读取剩余全部数据。
                0：返回空 bytes。
                >0：最多读取 size 字节。

        Returns:
            bytes
        """

        self._ensure_open()

        if not isinstance(
            size,
            int,
        ):
            raise TypeError(
                "size 必须是 int"
            )

        if size == 0:
            return b""

        if size < 0:
            return self._read_all()

        self._fill(size)

        data = bytes(
            self._buffer[:size]
        )

        del self._buffer[:size]

        return data

    def _fill(
        self,
        size: int,
    ) -> None:
        """填充缓冲区。

        直到：

        1. 缓冲区达到 size；
        2. HTTP 流结束。
        """

        while (
            len(self._buffer) < size
            and not self._eof
        ):

            chunk = self._next_chunk()

            if chunk is None:
                break

            self._buffer.extend(
                chunk
            )

    def _read_all(self) -> bytes:
        """读取剩余全部数据。"""

        while not self._eof:

            chunk = self._next_chunk()

            if chunk is None:
                break

            self._buffer.extend(
                chunk
            )

        data = bytes(
            self._buffer
        )

        self._buffer.clear()

        return data

    def _next_chunk(self) -> bytes | None:
        """读取下一块 HTTP 数据。"""

        if self._eof:
            return None

        try:

            chunk = next(
                self.iterator
            )

        except StopIteration:

            self._eof = True

            return None

        except requests.RequestException:

            self._eof = True

            self.close()

            raise

        # iter_content() 可能返回空 chunk。
        if not chunk:
            return b""

        return chunk

    # ==================================================
    # IO State
    # ==================================================

    @property
    def closed(self) -> bool:
        """是否已经关闭。"""

        return self._closed

    def readable(self) -> bool:
        """HTTP 流是否可读。"""

        return not self._closed

    def writable(self) -> bool:
        """HTTP 流是否可写。"""

        return False

    def seekable(self) -> bool:
        """HTTP 流是否支持 seek。"""

        return False

    def seek(
        self,
        *args,
        **kwargs,
    ):
        raise OSError(
            "HTTP stream does not support seek"
        )

    def tell(self) -> int:
        """HTTP 流不支持定位。"""

        raise OSError(
            "HTTP stream does not support tell"
        )

    # ==================================================
    # Close
    # ==================================================

    def close(self) -> None:
        """关闭 HTTP 流。"""

        if self._closed:
            return

        self._closed = True
        self._eof = True

        # 清理本地缓冲区。
        self._buffer.clear()

        self.response.close()

    def _ensure_open(self) -> None:

        if self._closed:
            raise ValueError(
                "I/O operation on closed HTTP stream"
            )

    # ==================================================
    # Context Manager
    # ==================================================

    def __enter__(self) -> "HttpStream":
        self._ensure_open()
        return self

    def __exit__(
        self,
        exc_type,
        exc,
        tb,
    ) -> None:

        self.close()

    # ==================================================
    # Destructor
    # ==================================================

    def __del__(self) -> None:
        """尽可能释放底层 HTTP 连接。"""

        try:
            self.close()
        except Exception:
            pass


class HttpFileSystem(FileSystem):
    """HTTP 只读文件系统。

    HTTP FileSystem 只负责：

    - open
    - exists
    - is_file
    - stat

    不支持：

    - write
    - delete
    - iterdir
    - compress
    - decompress
    """

    # HTTP HEAD fallback 状态码。
    HEAD_UNSUPPORTED_STATUS = {
        400,
        403,
        405,
        501,
    }

    DEFAULT_TIMEOUT = (
        10,
        30,
    )

    # ==================================================
    # Open
    # ==================================================

    def open(
        self,
        path: VirtualPath,
        mode: str = "rb",
        **kwargs: Any,
    ) -> HttpStream:
        """打开 HTTP 资源。

        只支持读取模式。
        """

        self._validate_read_mode(
            mode
        )

        url = self._url(
            path
        )

        timeout = kwargs.pop(
            "timeout",
            self.DEFAULT_TIMEOUT,
        )

        chunk_size = kwargs.pop(
            "chunk_size",
            HttpStream.DEFAULT_CHUNK_SIZE,
        )

        if kwargs:
            raise TypeError(
                "不支持的参数: "
                + ", ".join(
                    kwargs.keys()
                )
            )

        response = requests.get(
            url,
            stream=True,
            timeout=timeout,
        )

        try:

            response.raise_for_status()

        except Exception:

            response.close()

            raise

        return HttpStream(
            response,
            chunk_size=chunk_size,
        )

    # ==================================================
    # Exists
    # ==================================================

    def exists(
        self,
        path: VirtualPath,
    ) -> bool:
        """判断 HTTP 资源是否存在。"""

        url = self._url(
            path
        )

        try:

            response = requests.head(
                url,
                timeout=10,
                allow_redirects=True,
            )

            try:

                if response.status_code < 400:
                    return True

                if (
                    response.status_code
                    not in self.HEAD_UNSUPPORTED_STATUS
                ):
                    return False

            finally:
                response.close()

            # HEAD 不支持时使用 Range GET。
            return self._range_exists(
                url
            )

        except requests.RequestException:

            return False

    def _range_exists(
        self,
        url: str,
    ) -> bool:
        """通过 Range GET 判断资源是否存在。"""

        response = None

        try:

            response = requests.get(
                url,
                headers={
                    "Range": "bytes=0-0"
                },
                stream=True,
                timeout=10,
            )

            return (
                response.status_code < 400
            )

        except requests.RequestException:

            return False

        finally:

            if response is not None:
                response.close()

    # ==================================================
    # File
    # ==================================================

    def is_file(
        self,
        path: VirtualPath,
    ) -> bool:
        """HTTP 资源默认视为文件。

        HTTP 本身没有传统文件系统中的
        file / directory 概念。

        只要资源可以访问，就视为文件。
        """

        return self.exists(
            path
        )

    # ==================================================
    # Stat
    # ==================================================

    def stat(
        self,
        path: VirtualPath,
    ) -> dict[str, Any]:
        """获取 HTTP 资源元数据。"""

        url = self._url(
            path
        )

        response = None

        try:

            response = requests.head(
                url,
                timeout=10,
                allow_redirects=True,
            )

            if (
                response.status_code
                in self.HEAD_UNSUPPORTED_STATUS
            ):

                response.close()

                response = requests.get(
                    url,
                    headers={
                        "Range": "bytes=0-0"
                    },
                    stream=True,
                    timeout=10,
                )

            response.raise_for_status()

            return self._build_stat(
                response
            )

        except requests.RequestException:

            return {
                "size": None,
                "content_type": None,
                "mtime": None,
            }

        finally:

            if response is not None:
                response.close()

    @staticmethod
    def _build_stat(
        response: requests.Response,
    ) -> dict[str, Any]:
        """从 HTTP Response 构造 stat 信息。"""

        headers = response.headers

        content_length = headers.get(
            "Content-Length"
        )

        size = None

        if content_length:

            try:
                size = int(
                    content_length
                )
            except ValueError:
                size = None

        return {
            "size": size,
            "content_type": (
                headers.get(
                    "Content-Type"
                )
            ),
            "mtime": (
                headers.get(
                    "Last-Modified"
                )
            ),
            "etag": (
                headers.get(
                    "ETag"
                )
            ),
        }

    # ==================================================
    # Unsupported Operations
    # ==================================================

    def delete(
        self,
        path: VirtualPath,
    ) -> None:

        raise NotImplementedError(
            "HTTP filesystem is readonly"
        )

    def iterdir(
        self,
        path: VirtualPath,
    ):

        raise NotImplementedError(
            "HTTP filesystem does not support iterdir"
        )

    def compress(
        self,
        path: VirtualPath,
        target_path=None,
    ):

        raise NotImplementedError(
            "HTTP filesystem does not support compress"
        )

    def decompress(
        self,
        path: VirtualPath,
        target_path=None,
    ):

        raise NotImplementedError(
            "HTTP filesystem does not support decompress"
        )

    # ==================================================
    # Utils
    # ==================================================

    @staticmethod
    def _url(
        path: VirtualPath,
    ) -> str:
        """获取 HTTP URL。"""

        url = str(path)

        if not url.startswith(
            (
                "http://",
                "https://",
            )
        ):
            raise ValueError(
                f"不是 HTTP URL: {url}"
            )

        return url

    @staticmethod
    def _validate_read_mode(
        mode: str,
    ) -> None:
        """验证 HTTP 只读模式。"""

        if not isinstance(
            mode,
            str,
        ):
            raise TypeError(
                "mode 必须是 str"
            )

        if any(
            flag in mode
            for flag in (
                "w",
                "a",
                "x",
                "+",
            )
        ):
            raise OSError(
                "HTTP filesystem is readonly"
            )

        if "r" not in mode:
            raise ValueError(
                f"HTTP filesystem 不支持该模式: {mode}"
            )