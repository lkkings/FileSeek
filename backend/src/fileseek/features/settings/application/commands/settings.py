from dataclasses import dataclass


@dataclass(frozen=True)
class ReplaceClassifierLabelsCommand:
    document_labels: tuple[str, ...]
    image_labels: tuple[str, ...]
    video_labels: tuple[str, ...]


@dataclass(frozen=True)
class CreateStorageLocationCommand:
    name: str
    protocol: str
    endpoint: str
    root_path: str = ""
    account: str | None = None
    password: str | None = None
    id: str | None = None


@dataclass(frozen=True)
class UpdateStorageLocationCommand:
    location_id: str
    name: str
    protocol: str
    endpoint: str
    root_path: str = ""
    account: str | None = None
    password: str | None = None


@dataclass(frozen=True)
class DeleteStorageLocationCommand:
    location_id: str


@dataclass(frozen=True)
class TestStorageConnectionCommand:
    location_id: str
