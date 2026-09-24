from fileseek.infrastructure.fs.http import HttpFileSystem
from fileseek.infrastructure.fs.local import LocalFileSystem
from fileseek.infrastructure.fs.path import VirtualPath
from fileseek.infrastructure.fs.register import FileSystemRegistry


FileSystemRegistry.register(
    "file",
    LocalFileSystem()
)


FileSystemRegistry.register(
    "http",
    HttpFileSystem()
)


FileSystemRegistry.register(
    "https",
    HttpFileSystem()
)


__all__ = [
    "HttpFileSystem",
    "LocalFileSystem",
    "VirtualPath",
    "FileSystemRegistry"
]