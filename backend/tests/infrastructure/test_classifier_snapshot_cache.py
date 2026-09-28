from __future__ import annotations

from typing import Any

from fileseek.features.tasks.domain.ports import ClassifierLabelSnapshot
from fileseek.infrastructure.classifier.factory import (
    ClassifierFactory,
    get_classifier_for_snapshot,
)


def test_classifier_cache_reuses_snapshot_and_rebuilds_on_change(
    monkeypatch: Any,
) -> None:
    def fake_create(cls: type[ClassifierFactory], **kwargs: object) -> object:
        _ = cls, kwargs
        return object()

    monkeypatch.setattr(
        ClassifierFactory,
        "create",
        classmethod(fake_create),
    )
    get_classifier_for_snapshot.cache_clear()
    snapshot = ClassifierLabelSnapshot(
        document_labels=("合同",),
        image_labels=("照片",),
        video_labels=("课程",),
        version="version-1",
    )
    changed = ClassifierLabelSnapshot(
        document_labels=("发票",),
        image_labels=("照片",),
        video_labels=("课程",),
        version="version-2",
    )

    first = get_classifier_for_snapshot(snapshot)
    same = get_classifier_for_snapshot(snapshot)
    rebuilt = get_classifier_for_snapshot(changed)
    get_classifier_for_snapshot.cache_clear()

    assert first is same
    assert first is not rebuilt
