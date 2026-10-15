from __future__ import annotations

from collections.abc import Callable
from typing import Protocol
from urllib.parse import urlparse

from fileseek.features.search.application.dto import AgentAssistantMessage
from fileseek.features.search.application.ports import AgentConnection
from fileseek.features.search.domain.exceptions import AgentProviderError
from fileseek.features.settings.application.commands import (
    TestAgentSettingsCommand,
    UpdateAgentSettingsCommand,
)
from fileseek.features.settings.application.dto import (
    AgentSettingsDTO,
    ConnectionTestResultDTO,
)
from fileseek.features.settings.domain.entities import AgentSettings
from fileseek.features.settings.domain.repositories import AgentSettingsRepository
from fileseek.shared.domain.exceptions import ValidationError


class AgentConnectionTester(Protocol):
    async def test(self, connection: AgentConnection) -> AgentAssistantMessage: ...


def _validate_agent_settings(base_url: str, model: str) -> tuple[str, str]:
    normalized_base_url = base_url.strip()
    normalized_model = model.strip()
    if not normalized_base_url:
        raise ValidationError("Agent 地址不能为空")
    if not normalized_model:
        raise ValidationError("Agent 模型不能为空")

    parsed_url = urlparse(normalized_base_url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise ValidationError("Agent 地址必须是 http 或 https URL")
    return normalized_base_url, normalized_model


def agent_settings_to_dto(value: AgentSettings) -> AgentSettingsDTO:
    return AgentSettingsDTO(
        base_url=value.base_url,
        model=value.model,
        api_key_configured=value.is_configured,
    )


class GetAgentSettingsUseCase:
    def __init__(self, repository: AgentSettingsRepository) -> None:
        self.repository = repository

    async def execute(self) -> AgentSettingsDTO:
        settings = await self.repository.get() or AgentSettings()
        return agent_settings_to_dto(settings)


class UpdateAgentSettingsUseCase:
    def __init__(self, repository: AgentSettingsRepository) -> None:
        self.repository = repository

    async def execute(
        self,
        command: UpdateAgentSettingsCommand,
    ) -> AgentSettingsDTO:
        base_url, model = _validate_agent_settings(command.base_url, command.model)

        current = await self.repository.get()
        if command.api_key is None:
            api_key = current.api_key if current is not None else None
        else:
            api_key = command.api_key.strip() or None

        settings = await self.repository.save(
            AgentSettings(base_url=base_url, api_key=api_key, model=model)
        )
        return agent_settings_to_dto(settings)


class TestAgentSettingsUseCase:
    def __init__(
        self,
        repository: AgentSettingsRepository,
        connection_tester_factory: Callable[[AgentConnection], AgentConnectionTester],
    ) -> None:
        self.repository = repository
        self.connection_tester_factory = connection_tester_factory

    async def execute(
        self,
        command: TestAgentSettingsCommand,
    ) -> ConnectionTestResultDTO:
        base_url, model = _validate_agent_settings(command.base_url, command.model)
        current = await self.repository.get()
        api_key = (
            command.api_key.strip() or (current.api_key if current is not None else None)
            if command.api_key is not None
            else current.api_key
            if current is not None
            else None
        )
        if not api_key:
            raise ValidationError("Agent API Key 不能为空")

        connection = AgentConnection(
            base_url=base_url,
            api_key=api_key,
            model=model,
        )
        tester = self.connection_tester_factory(connection)
        try:
            await tester.test(connection)
        except AgentProviderError as exc:
            return ConnectionTestResultDTO(success=False, message=str(exc))
        return ConnectionTestResultDTO(success=True, message="Agent 连接成功")
