from fileseek.features.settings.domain.repositories import ClassifierLabelRepository
from fileseek.features.tasks.domain.ports import ClassifierLabelSnapshot


class TortoiseClassifierLabelProvider:
    def __init__(self, repository: ClassifierLabelRepository) -> None:
        self.repository = repository

    async def get_snapshot(self) -> ClassifierLabelSnapshot:
        labels = await self.repository.get_label_set()
        return ClassifierLabelSnapshot(
            document_labels=labels.document_labels,
            image_labels=labels.image_labels,
            video_labels=labels.video_labels,
            version=labels.version,
        )
