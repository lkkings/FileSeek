from dataclasses import dataclass


@dataclass(frozen=True)
class SettingsDTO:
    lib_root: str
    nas_enabled: bool


@dataclass(frozen=True)
class NASConnectionResultDTO:
    message: str
