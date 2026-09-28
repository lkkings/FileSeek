from fileseek.shared.domain.exceptions import ApplicationError


class StorageConnectionError(ApplicationError):
    """Storage location connection failure."""


class StorageBrowseUnsupportedError(ApplicationError):
    """The storage location cannot be browsed with the current adapter."""


class StorageBrowseUnavailableError(ApplicationError):
    """The requested storage directory is unavailable or outside its root."""


__all__ = [
    "StorageBrowseUnavailableError",
    "StorageBrowseUnsupportedError",
    "StorageConnectionError",
]
