

from fileseek.infrastructure.fs.base import FileSystem
# ==================================================
# Registry
# ==================================================

class FileSystemRegistry:

    _registry = {}


    @classmethod
    def register(cls, scheme, fs:FileSystem):

        cls._registry[scheme] = fs


    @classmethod
    def get(cls, scheme) -> FileSystem:

        if scheme not in cls._registry:

            raise RuntimeError(
                f"Unsupported scheme: {scheme}"
            )

        return cls._registry[scheme]

