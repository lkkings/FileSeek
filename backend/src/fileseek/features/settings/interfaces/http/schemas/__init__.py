"""Settings HTTP schemas."""

from fileseek.features.settings.interfaces.http.schemas.nas import NASTestRequest
from fileseek.features.settings.interfaces.http.schemas.settings import (
    SettingsResponse,
    SettingsUpdateRequest,
)

__all__ = [
    "NASTestRequest",
    "SettingsResponse",
    "SettingsUpdateRequest",
]
