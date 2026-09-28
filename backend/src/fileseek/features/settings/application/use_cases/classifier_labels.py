from fileseek.features.settings.application.commands import (
    ReplaceClassifierLabelsCommand,
)
from fileseek.features.settings.application.dto import ClassifierLabelsDTO
from fileseek.features.settings.application.mappers import classifier_label_set_to_dto
from fileseek.features.settings.application.queries import GetClassifierLabelsQuery
from fileseek.features.settings.domain.entities import ClassifierLabelSet
from fileseek.features.settings.domain.repositories import ClassifierLabelRepository
from fileseek.shared.domain.exceptions import ValidationError


class GetClassifierLabelsUseCase:
    def __init__(self, repository: ClassifierLabelRepository) -> None:
        self.repository = repository

    async def execute(self, query: GetClassifierLabelsQuery) -> ClassifierLabelsDTO:
        _ = query
        return classifier_label_set_to_dto(await self.repository.get_label_set())


class ReplaceClassifierLabelsUseCase:
    def __init__(self, repository: ClassifierLabelRepository) -> None:
        self.repository = repository

    async def execute(
        self,
        command: ReplaceClassifierLabelsCommand,
    ) -> ClassifierLabelsDTO:
        categories = {
            "document": command.document_labels,
            "image": command.image_labels,
            "video": command.video_labels,
        }
        normalized: dict[str, tuple[str, ...]] = {}
        for category, labels in categories.items():
            values = tuple(label.strip() for label in labels if label.strip())
            if len(values) != len(set(values)):
                raise ValidationError(f"{category} 标签存在重复")
            normalized[category] = values

        label_set = ClassifierLabelSet(
            document_labels=normalized["document"],
            image_labels=normalized["image"],
            video_labels=normalized["video"],
        )
        await self.repository.replace_label_set(label_set)
        return classifier_label_set_to_dto(label_set)
