from __future__ import annotations

import pytest

from fileseek.features.search.application.dto import (
    AgentAssistantMessage,
    AgentToolCall,
    EnhancedSearchProgressDTO,
    FileDTO,
    SearchResultsDTO,
)
from fileseek.features.search.application.ports import AgentConnection
from fileseek.features.search.application.queries import EnhancedSearchQuery
from fileseek.features.search.application.use_cases import EnhancedSearchUseCase
from fileseek.features.search.interfaces.http.mappers import (
    enhanced_search_progress_to_event,
)
from fileseek.shared.utils.cache import TTLLRUCache


def result_dto() -> SearchResultsDTO:
    return SearchResultsDTO(
        items=[
            FileDTO(
                file_id="file-1",
                file_name="Cat.jpg",
                file_type="jpg",
                category="image",
                path="/library/Cat.jpg",
                size=1024,
                modified="2026-10-01T00:00:00",
                tags=[],
                score=0.9,
            )
        ],
        counter={"document": 0, "image": 1, "video": 0},
        total=1,
        page_number=1,
        page_size=20,
    )


def test_progress_event_shapes_serialize_every_event_type() -> None:
    events = [
        EnhancedSearchProgressDTO(type="status", phase="starting", message="正在理解搜索意图"),
        EnhancedSearchProgressDTO(
            type="reasoning",
            round_number=1,
            content="先按用户描述检索一次",
        ),
        EnhancedSearchProgressDTO(
            type="tool_call",
            round_number=1,
            tool_name="search_files",
            query="旅行 猫",
            categories=("image",),
            name_query=None,
        ),
        EnhancedSearchProgressDTO(
            type="tool_result",
            round_number=1,
            tool_name="search_files",
            query="旅行 猫",
            categories=("image",),
            candidate_count=1,
            total=1,
        ),
        EnhancedSearchProgressDTO(type="result", result=result_dto()),
        EnhancedSearchProgressDTO(type="error", error="Agent 请求超时"),
    ]

    payloads = [
        enhanced_search_progress_to_event(event).model_dump(mode="json") for event in events
    ]

    assert [payload["type"] for payload in payloads] == [
        "status",
        "reasoning",
        "tool_call",
        "tool_result",
        "result",
        "error",
    ]
    assert payloads[0]["phase"] == "starting"
    assert payloads[1]["round_number"] == 1
    assert payloads[2]["query"] == "旅行 猫"
    assert payloads[3]["candidate_count"] == 1
    assert payloads[4]["result"]["items"][0]["file_id"] == "file-1"
    assert payloads[5]["error"] == "Agent 请求超时"


def test_progress_event_serialization_rejects_sensitive_or_unknown_fields() -> None:
    payload = enhanced_search_progress_to_event(
        EnhancedSearchProgressDTO(type="status", phase="starting")
    ).model_dump(mode="json")

    for field in ("api_key", "provider_response", "messages", "reasoning"):
        with pytest.raises(ValueError, match="Extra inputs are not permitted"):
            enhanced_search_progress_to_event(
                EnhancedSearchProgressDTO(type="status", phase="starting")
            ).model_validate({**payload, field: "sensitive-value"})

    serialized_keys = set(payload)
    assert "api_key" not in serialized_keys
    assert "provider_response" not in serialized_keys
    assert "messages" not in serialized_keys
    assert "reasoning" not in serialized_keys


class ScriptedAgentClient:
    def __init__(self, responses: list[AgentAssistantMessage]) -> None:
        self.responses = list(responses)

    async def complete(self, messages, tools) -> AgentAssistantMessage:
        if not self.responses:
            raise AssertionError("unexpected agent completion")
        return self.responses.pop(0)


class ScriptedSearchUseCase:
    def __init__(self, results: list[SearchResultsDTO]) -> None:
        self.results = list(results)

    async def execute(self, query) -> SearchResultsDTO:
        if not self.results:
            raise AssertionError("unexpected search")
        return self.results.pop(0)


class StaticAgentSettingsProvider:
    def __init__(self, connection: AgentConnection | None) -> None:
        self.connection = connection

    async def get(self) -> AgentConnection | None:
        return self.connection


def create_use_case(
    agent_responses: list[AgentAssistantMessage],
    search_results: list[SearchResultsDTO],
) -> EnhancedSearchUseCase:
    agent_client = ScriptedAgentClient(agent_responses)
    return EnhancedSearchUseCase(
        ScriptedSearchUseCase(search_results),
        StaticAgentSettingsProvider(
            AgentConnection(
                base_url="https://api.example.com/v1",
                api_key="secret-key",
                model="retrieval-expert",
            )
        ),
        lambda _: agent_client,
        TTLLRUCache(maxsize=8, ttl=60),
    )


@pytest.mark.asyncio
async def test_execute_stream_emits_round_level_progress_and_one_result() -> None:
    use_case = create_use_case(
        [
            AgentAssistantMessage(
                content="先按用户描述检索一次",
                tool_calls=(AgentToolCall("call-1", "search_files", '{"query":"cat"}'),),
            ),
            AgentAssistantMessage(
                content=None,
                tool_calls=(
                    AgentToolCall(
                        "call-2",
                        "submit_selected_file_ids",
                        '{"file_ids":["file-1"]}',
                    ),
                ),
            ),
        ],
        [result_dto()],
    )

    events = [
        event
        async for event in use_case.execute_stream(
            EnhancedSearchQuery(query="cat", folder_id=None, page_size=20)
        )
    ]

    assert [event.type for event in events] == [
        "status",
        "status",
        "reasoning",
        "tool_call",
        "tool_result",
        "status",
        "tool_call",
        "status",
        "status",
        "result",
    ]
    assert events[5].message == "第 2 轮：正在分析检索结果并决定是否继续检索"
    assert events[-1].result is not None
    assert events[-1].result.total == 1
    assert sum(event.type == "result" for event in events) == 1


@pytest.mark.asyncio
async def test_execute_stream_reports_cached_result_without_running_agent() -> None:
    use_case = create_use_case(
        [
            AgentAssistantMessage(
                content=None,
                tool_calls=(
                    AgentToolCall(
                        "call-1",
                        "submit_selected_file_ids",
                        '{"file_ids":["file-1"]}',
                    ),
                ),
            )
        ],
        [result_dto()],
    )
    query = EnhancedSearchQuery(query="cat", folder_id=None, page_size=20)
    await use_case.execute(query)
    use_case.agent_client_factory = lambda _: (_ for _ in ()).throw(
        AssertionError("agent must not run")
    )

    events = [event async for event in use_case.execute_stream(query)]

    assert [event.type for event in events] == ["status", "result"]
    assert events[0].phase == "cache_hit"


@pytest.mark.asyncio
async def test_execute_stream_ends_with_one_error_event() -> None:
    use_case = create_use_case(
        [AgentAssistantMessage(content=None, tool_calls=())],
        [],
    )

    events = [
        event
        async for event in use_case.execute_stream(
            EnhancedSearchQuery(query="cat", folder_id=None, page_size=20)
        )
    ]

    assert events[-1].type == "error"
    assert events[-1].error == "Agent 未提交文件 ID"
    assert sum(event.type == "error" for event in events) == 1
