from dataclasses import dataclass


@dataclass(frozen=True)
class GetClassifierLabelsQuery:
    pass


@dataclass(frozen=True)
class ListStorageLocationsQuery:
    pass


@dataclass(frozen=True)
class ListStorageDirectoryQuery:
    storage_id: str
    path: str = ""
