from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Literal

StorageLocationType = Literal["local", "nas", "external"]
StorageProtocol = Literal["file", "mounted", "smb", "nfs", "webdav", "http"]
StorageStatus = Literal["active", "deleted"]


@dataclass(frozen=True)
class StorageLocation:
    id: str
    type: StorageLocationType
    name: str
    protocol: StorageProtocol
    endpoint: str
    root_path: str = ""
    account: str | None = None
    password: str | None = None
    status: StorageStatus = "active"
    is_system: bool = False

    @property
    def is_active(self) -> bool:
        return self.status == "active"

    @property
    def is_manageable(self) -> bool:
        return self.type in {"local", "nas"}


@dataclass(frozen=True)
class ClassifierLabelSet:
    document_labels: tuple[str, ...] = ()
    image_labels: tuple[str, ...] = ()
    video_labels: tuple[str, ...] = ()

    @property
    def version(self) -> str:
        value = "\n".join(
            (
                *sorted(self.document_labels),
                "\n",
                *sorted(self.image_labels),
                "\n",
                *sorted(self.video_labels),
            )
        )
        return sha256(value.encode("utf-8")).hexdigest()

    @property
    def is_empty(self) -> bool:
        return not (self.document_labels or self.image_labels or self.video_labels)


@dataclass(frozen=True)
class AgentSettings:
    id: str = "default"
    base_url: str = ""
    api_key: str | None = None
    model: str = ""

    @property
    def is_configured(self) -> bool:
        return bool(
            self.base_url.strip() and self.api_key and self.api_key.strip() and self.model.strip()
        )
