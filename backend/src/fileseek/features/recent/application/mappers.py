from fileseek.features.recent.application.dto import RecentAccessDTO
from fileseek.features.recent.domain.entities import RecentAccessRecord


def recent_access_to_dto(value: RecentAccessRecord) -> RecentAccessDTO:
    return RecentAccessDTO(value.file_id, value.accessed_at)
