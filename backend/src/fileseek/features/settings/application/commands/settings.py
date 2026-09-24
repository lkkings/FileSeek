from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UpdateSettingsCommand:
    lib_root: str


@dataclass(frozen=True)
class TestNASConnectionCommand:
    protocol: str
    host: str
    share_path: str
    username: str
    password: str
