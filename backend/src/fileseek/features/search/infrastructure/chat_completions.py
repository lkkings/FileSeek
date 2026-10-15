from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from json import JSONDecodeError, loads
from typing import cast

import httpx

from fileseek.features.search.application.dto import (
    AgentAssistantMessage,
    AgentToolCall,
)
from fileseek.features.search.domain.exceptions import AgentProviderError

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 180


class OpenAIChatCompletionsClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._endpoint = f"{base_url.rstrip('/')}/chat/completions"
        self._api_key = api_key
        self._model = model
        self._http_client = http_client or httpx.AsyncClient(timeout=timeout_seconds)

    async def complete(
        self,
        messages: Sequence[Mapping[str, object]],
        tools: Sequence[Mapping[str, object]],
    ) -> AgentAssistantMessage:
        try:
            response = await self._http_client.post(
                self._endpoint,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": self._model,
                    "messages": [dict(message) for message in messages],
                    "tools": [dict(tool) for tool in tools],
                },
            )
        except httpx.TimeoutException as exc:
            raise AgentProviderError("Agent 请求超时") from exc
        except httpx.HTTPError as exc:
            raise AgentProviderError("无法连接 Agent 服务") from exc

        if response.status_code < 200 or response.status_code >= 300:
            logger.warning(
                "Agent request failed: endpoint=%s model=%s status=%s",
                self._endpoint,
                self._model,
                response.status_code,
            )
            if response.status_code == 401:
                raise AgentProviderError(
                    "Agent 服务认证失败: HTTP 401，请检查 API Key 和模型权限",
                )
            if response.status_code == 403:
                raise AgentProviderError(
                    "Agent 服务拒绝访问: HTTP 403，请检查模型权限",
                )
            raise AgentProviderError(f"Agent 服务请求失败: HTTP {response.status_code}")

        try:
            payload = cast("dict[str, object]", loads(response.text))
            return _parse_assistant_message(payload)
        except (JSONDecodeError, TypeError, KeyError, ValueError) as exc:
            raise AgentProviderError("Agent 返回格式无效") from exc


def _parse_assistant_message(payload: dict[str, object]) -> AgentAssistantMessage:
    choices = _dict_sequence(payload.get("choices"))
    if not choices:
        raise ValueError("missing choices")
    message = _dict(choices[0].get("message"))
    content = message.get("content")
    if content is not None and not isinstance(content, str):
        raise ValueError("invalid content")

    raw_tool_calls = message.get("tool_calls")
    tool_calls = (
        (_parse_tool_call(item) for item in _object_sequence(raw_tool_calls))
        if raw_tool_calls is not None
        else ()
    )
    return AgentAssistantMessage(content=content, tool_calls=tuple(tool_calls))


def _parse_tool_call(value: object) -> AgentToolCall:
    item = _dict(value)
    function = _dict(item.get("function"))
    tool_call_id = _string(item.get("id"))
    name = _string(function.get("name"))
    arguments = _string(function.get("arguments"))
    if not tool_call_id or not name or arguments is None:
        raise ValueError("invalid tool call")
    if item.get("type") != "function":
        raise ValueError("unsupported tool call type")
    return AgentToolCall(id=tool_call_id, name=name, arguments=arguments)


def _dict(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise TypeError("expected object")
    return cast("dict[str, object]", value)


def _dict_sequence(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise TypeError("expected list")
    return [_dict(item) for item in value]


def _object_sequence(value: object) -> list[object]:
    if not isinstance(value, list):
        raise TypeError("expected list")
    return value


def _string(value: object) -> str | None:
    return value if isinstance(value, str) else None
