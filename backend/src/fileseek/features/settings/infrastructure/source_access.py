from __future__ import annotations

from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from http.client import HTTPResponse
from pathlib import Path
from typing import IO, cast
from urllib.error import URLError
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen

from fileseek.features.library.application.ports import (
    FileSourcePort,
    SourceFile,
    SourceMetadata,
)
from fileseek.features.library.domain.exceptions import SourceUnavailableError
from fileseek.features.settings.domain.repositories import StorageLocationRepository


class LocalSourceFile(SourceFile):
    def __init__(self, path: Path) -> None:
        self.path = path

    def exists(self) -> bool:
        return self.path.exists()

    def is_file(self) -> bool:
        return self.path.is_file()

    def stat(self) -> dict[str, int | float]:
        metadata = self.path.stat()
        return {"size": metadata.st_size, "mtime": metadata.st_mtime}

    def open(self, mode: str = "rb") -> IO[bytes]:
        return self.path.open(mode)

    def unlink(self, missing_ok: bool = False) -> None:
        self.path.unlink(missing_ok=missing_ok)

    def __str__(self) -> str:
        return str(self.path)


class NasSourceFile(LocalSourceFile):
    def __init__(self, root: Path, source_path: str) -> None:
        self.root = root.resolve(strict=False)
        resolved = (self.root / Path(source_path)).resolve(strict=False)
        if not resolved.is_relative_to(self.root):
            raise SourceUnavailableError("NAS 来源路径超出挂载根目录")
        super().__init__(resolved)

    @property
    def relative_path(self) -> Path:
        return self.path.relative_to(self.root)


class _RemoteSourceReader:
    def __init__(self, uri: str, response: HTTPResponse | None) -> None:
        self.uri = uri
        self.response = response
        self.position = 0

    def read(self, size: int = -1) -> bytes:
        if self.response is None:
            raise OSError("来源流已关闭")
        data = self.response.read(size)
        self.position += len(data)
        return data

    def seek(self, offset: int, whence: int = 0) -> int:
        if whence != 0:
            raise OSError("远程来源只支持绝对定位")
        if offset == self.position:
            return self.position
        self.close()
        request = Request(self.uri, headers={"Range": f"bytes={offset}-"})  # noqa: S310
        self.response = _open_remote(request)
        self.position = offset
        return self.position

    def close(self) -> None:
        if self.response is not None:
            self.response.close()
            self.response = None

    def __enter__(self) -> _RemoteSourceReader:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


class ExternalUriSourceFile(SourceFile):
    def __init__(self, uri: str) -> None:
        self.uri = uri

    def exists(self) -> bool:
        try:
            self.stat()
        except SourceUnavailableError:
            return False
        else:
            return True

    def is_file(self) -> bool:
        return self.exists()

    def stat(self) -> dict[str, object]:
        size: str | None
        modified: str | None
        try:
            with _open_remote(Request(self.uri, method="HEAD")) as response:  # noqa: S310
                size = response.headers.get("Content-Length")
                modified = response.headers.get("Last-Modified")
        except (OSError, URLError, ValueError) as exc:
            raise SourceUnavailableError(f"来源文件不可访问: {self.uri}") from exc
        if size is None:
            raise SourceUnavailableError(f"来源文件元数据不可用: {self.uri}")
        return {
            "size": int(size),
            "mtime": parsedate_to_datetime(modified).timestamp()
            if modified
            else datetime.now(UTC).timestamp(),
        }

    def open(self, mode: str = "rb") -> IO[bytes]:
        if mode != "rb":
            raise OSError("远程来源只支持读取")
        try:
            request = Request(self.uri)  # noqa: S310
            reader = _RemoteSourceReader(self.uri, _open_remote(request))
            return cast(IO[bytes], reader)
        except (OSError, URLError) as exc:
            raise SourceUnavailableError(f"来源文件不可访问: {self.uri}") from exc

    def unlink(self, missing_ok: bool = False) -> None:
        _ = missing_ok
        raise OSError("远程来源不支持删除")

    def __str__(self) -> str:
        return self.uri


def _open_remote(request: Request) -> HTTPResponse:
    parsed = urlparse(request.full_url)
    if parsed.scheme not in {"http", "https"}:
        raise SourceUnavailableError(f"不支持的外部来源协议: {parsed.scheme}")
    return cast(HTTPResponse, urlopen(request))  # noqa: S310



def _mounted_source(root_value: str, source_path: str) -> SourceFile:
    return NasSourceFile(Path(root_value), source_path)


def _local_source(source_path: str) -> SourceFile:
    parsed = urlparse(source_path)
    if parsed.scheme == "file":
        return LocalSourceFile(Path(unquote(parsed.path)))
    return LocalSourceFile(Path(source_path))


def _external_source(source_path: str) -> SourceFile:
    parsed = urlparse(source_path)
    if parsed.scheme == "file":
        return _local_source(source_path)
    if parsed.scheme in {"http", "https"}:
        if ".." in parsed.path.split("/"):
            raise SourceUnavailableError("来源路径不能包含上级目录")
        return ExternalUriSourceFile(source_path)
    raise SourceUnavailableError(f"不支持的外部来源协议: {parsed.scheme or 'local'}")


class StorageSourceResolver(FileSourcePort):
    def __init__(self, repository: StorageLocationRepository) -> None:
        self.repository = repository

    async def resolve(
        self,
        storage_id: str,
        source_path: str,
    ) -> SourceFile:
        location = await self.repository.get_by_id(storage_id)
        if location is None:
            raise SourceUnavailableError(f"存储位置不存在: {storage_id}")

        if ".." in Path(source_path).parts:
            raise SourceUnavailableError("来源路径不能包含上级目录")

        if location.type in {"local", "external"}:
            if location.type == "external":
                return _external_source(source_path)
            return _local_source(source_path)

        if location.protocol != "mounted":
            raise SourceUnavailableError(
                f"存储协议暂不支持直接读取: {location.protocol}"
            )

        return _mounted_source(
            location.root_path or location.endpoint,
            source_path,
        )

    async def read_metadata(
        self,
        storage_id: str,
        source_path: str,
    ) -> SourceMetadata:
        source = await self.resolve(storage_id, source_path)
        if not source.exists() or not source.is_file():
            raise SourceUnavailableError(f"来源文件不可访问: {source_path}")

        try:
            stat = source.stat()
        except OSError as exc:
            raise SourceUnavailableError(f"来源文件不可访问: {source_path}") from exc
        size_value = stat.get("size")
        if not isinstance(size_value, (int, float)):
            raise SourceUnavailableError(f"来源文件元数据不可用: {source_path}")

        modified_value = stat.get("mtime")
        if modified_value is not None and not isinstance(
            modified_value,
            (int, float, str),
        ):
            raise SourceUnavailableError(f"来源文件元数据不可用: {source_path}")
        modified = (
            datetime.fromtimestamp(float(modified_value))
            if modified_value is not None
            else datetime.now(UTC)
        )
        return SourceMetadata(size=int(size_value), modified=modified)
