from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ClassifierLabelSnapshot:
    document_labels: tuple[str, ...]
    image_labels: tuple[str, ...]
    video_labels: tuple[str, ...]
    version: str

    @classmethod
    def from_metadata(
        cls,
        metadata: dict[str, object] | None,
    ) -> ClassifierLabelSnapshot:
        if metadata is None:
            raise ValueError("任务缺少分类标签快照")

        labels = metadata.get("classifier_labels")
        version = metadata.get("classifier_label_version")
        if not isinstance(labels, dict) or not isinstance(version, str):
            raise ValueError("任务分类标签快照格式无效")

        def read_tuple(category: str) -> tuple[str, ...]:
            value = labels.get(category)
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                raise ValueError(f"任务分类标签格式无效: {category}")
            return tuple(value)

        return cls(
            document_labels=read_tuple("document"),
            image_labels=read_tuple("image"),
            video_labels=read_tuple("video"),
            version=version,
        )

    def as_metadata(self) -> dict[str, object]:
        return {
            "classifier_labels": {
                "document": list(self.document_labels),
                "image": list(self.image_labels),
                "video": list(self.video_labels),
            },
            "classifier_label_version": self.version,
        }


class ClassifierLabelProvider(Protocol):
    async def get_snapshot(self) -> ClassifierLabelSnapshot: ...
