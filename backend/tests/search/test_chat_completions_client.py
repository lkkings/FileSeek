from __future__ import annotations

import logging

import httpx
import pytest

from fileseek.features.search.domain.exceptions import AgentProviderError
from fileseek.features.search.infrastructure.chat_completions import (
    DEFAULT_TIMEOUT_SECONDS,
    OpenAIChatCompletionsClient,
)


def create_client(handler) -> OpenAIChatCompletionsClient:
    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport)
    return OpenAIChatCompletionsClient(
        base_url="https://api.example.com/v1",
        api_key="secret-key",
        model="retrieval-expert",
        http_client=http_client,
    )


@pytest.mark.asyncio
async def test_chat_completions_allows_long_agent_rounds() -> None:
    client = OpenAIChatCompletionsClient(
        base_url="https://api.example.com/v1",
        api_key="secret-key",
        model="retrieval-expert",
    )

    try:
        assert client._http_client.timeout == httpx.Timeout(DEFAULT_TIMEOUT_SECONDS)
        assert DEFAULT_TIMEOUT_SECONDS >= 180
    finally:
        await client._http_client.aclose()


@pytest.mark.asyncio
async def test_chat_completions_returns_tool_calls() -> None:
    seen_headers: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.update(request.headers)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call-1",
                                    "type": "function",
                                    "function": {
                                        "name": "search_files",
                                        "arguments": '{"query":"cat"}',
                                    },
                                }
                            ],
                        }
                    }
                ]
            },
        )

    client = create_client(handler)
    result = await client.complete(
        [{"role": "user", "content": "find cat photos"}],
        [{"type": "function", "function": {"name": "search_files"}}],
    )

    assert seen_headers["authorization"] == "Bearer secret-key"
    assert result.content is None
    assert result.tool_calls[0].id == "call-1"
    assert result.tool_calls[0].name == "search_files"
    assert result.tool_calls[0].arguments == '{"query":"cat"}'


@pytest.mark.asyncio
async def test_chat_completions_rejects_invalid_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": []})

    client = create_client(handler)

    with pytest.raises(AgentProviderError, match="格式无效"):
        await client.complete([{"role": "user", "content": "find files"}], [])


@pytest.mark.asyncio
async def test_chat_completions_redacts_provider_failures(caplog) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            json={"error": {"message": "invalid secret-key"}},
        )

    client = create_client(handler)

    with (
        pytest.raises(AgentProviderError) as error,
        caplog.at_level(
            logging.WARNING,
            logger="fileseek.features.search.infrastructure.chat_completions",
        ),
    ):
        await client.complete([{"role": "user", "content": "find files"}], [])

    assert "secret-key" not in str(error.value)
    assert "认证失败" in str(error.value)
    assert "API Key" in str(error.value)
    assert "secret-key" not in caplog.text
    assert "status=401" in caplog.text
    assert "model=retrieval-expert" in caplog.text
