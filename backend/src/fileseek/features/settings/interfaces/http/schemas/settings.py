from pydantic import BaseModel, ConfigDict, Field


class ClassifierLabelsRequest(BaseModel):
    document_labels: list[str] = Field(alias="document_labels")
    image_labels: list[str] = Field(alias="image_labels")
    video_labels: list[str] = Field(alias="video_labels")

    model_config = ConfigDict(populate_by_name=True)


class ClassifierLabelsResponse(BaseModel):
    document_labels: list[str] = Field(alias="document_labels")
    image_labels: list[str] = Field(alias="image_labels")
    video_labels: list[str] = Field(alias="video_labels")
    version: str

    model_config = ConfigDict(populate_by_name=True)


class AgentSettingsRequest(BaseModel):
    base_url: str = Field(alias="base_url")
    model: str
    api_key: str | None = Field(default=None, alias="api_key")

    model_config = ConfigDict(populate_by_name=True)


class AgentSettingsResponse(BaseModel):
    base_url: str = Field(alias="base_url")
    model: str
    api_key_configured: bool = Field(alias="api_key_configured")

    model_config = ConfigDict(populate_by_name=True)


class StorageLocationCreateRequest(BaseModel):
    id: str | None = None
    name: str
    protocol: str
    endpoint: str
    root_path: str = Field(default="", alias="root_path")
    account: str | None = None
    password: str | None = None

    model_config = ConfigDict(populate_by_name=True)


class StorageLocationUpdateRequest(BaseModel):
    name: str
    protocol: str
    endpoint: str
    root_path: str = Field(default="", alias="root_path")
    account: str | None = None
    password: str | None = None

    model_config = ConfigDict(populate_by_name=True)


class StorageLocationResponse(BaseModel):
    id: str
    type: str
    name: str
    protocol: str
    endpoint: str
    root_path: str = Field(alias="root_path")
    account: str | None
    status: str
    is_system: bool = Field(alias="is_system")

    model_config = ConfigDict(populate_by_name=True)


class StorageLocationDeletionResponse(BaseModel):
    id: str
    status: str
    affected_files: int = Field(alias="affected_files")

    model_config = ConfigDict(populate_by_name=True)


class ConnectionTestResponse(BaseModel):
    success: bool
    message: str


class StorageDirectoryEntryResponse(BaseModel):
    name: str
    kind: str
    source_path: str = Field(alias="source_path")
    size: int
    modified: str

    model_config = ConfigDict(populate_by_name=True)


class StorageDirectoryResponse(BaseModel):
    current_path: str = Field(alias="current_path")
    entries: list[StorageDirectoryEntryResponse]

    model_config = ConfigDict(populate_by_name=True)
