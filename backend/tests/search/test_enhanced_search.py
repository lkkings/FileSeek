from __future__ import annotations

import pytest

from fileseek.features.search.application.dto import (
    AgentAssistantMessage,
    AgentToolCall,
    FileDTO,
    SearchResultsDTO,
)
from fileseek.features.search.application.enhanced_search_tools import ENHANCED_SEARCH_TOOLS
from fileseek.features.search.application.ports import AgentConnection
from fileseek.features.search.application.queries import (
    EnhancedSearchQuery,
    FileSortBy,
    SearchFilesQuery,
    SortOrder,
)
from fileseek.features.search.application.use_cases import EnhancedSearchUseCase
from fileseek.features.search.domain.exceptions import AgentProviderError
from fileseek.shared.domain.exceptions import ValidationError
from fileseek.shared.utils.cache import TTLLRUCache


def file_dto(
    file_id: str,
    category: str,
    score: float,
    *,
    size: int = 10,
) -> FileDTO:
    return FileDTO(
        file_id=file_id,
        file_name=f"{file_id}.txt",
        file_type="txt",
        category=category,
        path=f"/library/{file_id}.txt",
        size=size,
        modified="2026-10-01T00:00:00",
        tags=[],
        score=score,
    )


def tool_call(name: str, arguments: str, call_id: str) -> AgentToolCall:
    return AgentToolCall(id=call_id, name=name, arguments=arguments)


def test_agent_search_tool_excludes_client_controlled_parameters() -> None:
    search_tool = next(
        tool for tool in ENHANCED_SEARCH_TOOLS if tool["function"]["name"] == "search_files"
    )
    parameters = search_tool["function"]["parameters"]

    assert "folder_id" not in parameters["properties"]
    assert "page_number" not in parameters["properties"]
    assert "page_size" not in parameters["properties"]
    assert "sort_by" not in parameters["properties"]
    assert "sort_order" not in parameters["properties"]


def assistant(*tool_calls: AgentToolCall) -> AgentAssistantMessage:
    return AgentAssistantMessage(content=None, tool_calls=tool_calls)


class ScriptedAgentClient:
    def __init__(self, responses: list[AgentAssistantMessage]) -> None:
        self.responses = list(responses)
        self.requests: list[tuple[int, int]] = []

    async def complete(self, messages, tools) -> AgentAssistantMessage:
        self.requests.append((len(messages), len(tools)))
        if not self.responses:
            raise AssertionError("unexpected agent completion")
        return self.responses.pop(0)


class ScriptedSearchUseCase:
    def __init__(self, results: list[SearchResultsDTO]) -> None:
        self.results = list(results)
        self.queries: list[SearchFilesQuery] = []

    async def execute(self, query: SearchFilesQuery) -> SearchResultsDTO:
        self.queries.append(query)
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
    *,
    configured: bool = True,
    max_tool_rounds: int = 8,
) -> tuple[EnhancedSearchUseCase, ScriptedAgentClient, ScriptedSearchUseCase]:
    agent_client = ScriptedAgentClient(agent_responses)
    search_use_case = ScriptedSearchUseCase(search_results)
    connection = (
        AgentConnection(
            base_url="https://api.example.com/v1",
            api_key="secret-key",
            model="retrieval-expert",
        )
        if configured
        else None
    )
    use_case = EnhancedSearchUseCase(
        search_use_case,
        StaticAgentSettingsProvider(connection),
        lambda _: agent_client,
        TTLLRUCache(maxsize=8, ttl=60),
        max_tool_rounds=max_tool_rounds,
    )
    return use_case, agent_client, search_use_case


@pytest.mark.asyncio
async def test_enhanced_search_runs_multiple_tools_and_filters_verified_ids() -> None:
    use_case, agent_client, search_use_case = create_use_case(
        [
            assistant(tool_call("search_files", '{"query":"cat"}', "call-1")),
            assistant(tool_call("search_files", '{"query":"travel"}', "call-2")),
            assistant(
                tool_call(
                    "submit_selected_file_ids",
                    '{"file_ids":["file-1","file-3","missing"]}',
                    "call-3",
                )
            ),
        ],
        [
            SearchResultsDTO(
                items=[file_dto("file-1", "document", 0.8), file_dto("file-2", "image", 0.4)],
                counter={"document": 1, "image": 1, "video": 0},
                total=2,
                page_number=1,
                page_size=20,
            ),
            SearchResultsDTO(
                items=[file_dto("file-3", "video", 0.9)],
                counter={"document": 0, "image": 0, "video": 1},
                total=1,
                page_number=1,
                page_size=20,
            ),
        ],
    )

    result = await use_case.execute(
        EnhancedSearchQuery(query="猫的旅行照片", folder_id="folder-1", page_size=2)
    )

    assert [item.file_id for item in result.items] == ["file-3", "file-1"]
    assert result.total == 2
    assert result.counter == {"document": 1, "image": 0, "video": 1}
    assert result.page_number == 1
    assert result.page_size == 2
    assert [query.query for query in search_use_case.queries] == ["cat", "travel"]
    assert [query.folder_id for query in search_use_case.queries] == ["folder-1", "folder-1"]
    assert len(agent_client.requests) == 3


@pytest.mark.asyncio
async def test_enhanced_search_rejects_unknown_tool() -> None:
    use_case, _, _ = create_use_case(
        [assistant(tool_call("delete_files", "{}", "call-1"))],
        [],
    )

    with pytest.raises(AgentProviderError, match="未知工具"):
        await use_case.execute(EnhancedSearchQuery(query="find files", folder_id=None))


@pytest.mark.asyncio
async def test_enhanced_search_rejects_missing_submission() -> None:
    use_case, _, _ = create_use_case(
        [AgentAssistantMessage(content="I found files", tool_calls=())],
        [],
    )

    with pytest.raises(AgentProviderError, match="未提交"):
        await use_case.execute(EnhancedSearchQuery(query="find files", folder_id=None))


@pytest.mark.asyncio
async def test_enhanced_search_limits_tool_rounds() -> None:
    use_case, agent_client, search_use_case = create_use_case(
        [assistant(tool_call("search_files", '{"query":"cat"}', "call-1"))] * 3,
        [
            SearchResultsDTO(
                items=[file_dto("file-1", "document", 0.8)],
                counter={"document": 1, "image": 0, "video": 0},
                total=1,
            )
        ]
        * 3,
        max_tool_rounds=2,
    )

    with pytest.raises(AgentProviderError, match="次数超限"):
        await use_case.execute(EnhancedSearchQuery(query="find files", folder_id=None))

    assert len(agent_client.requests) == 2
    assert len(search_use_case.queries) == 2


@pytest.mark.asyncio
async def test_enhanced_search_requires_configuration() -> None:
    use_case, agent_client, search_use_case = create_use_case(
        [],
        [],
        configured=False,
    )

    with pytest.raises(ValidationError, match="未配置"):
        await use_case.execute(EnhancedSearchQuery(query="find files", folder_id=None))

    assert agent_client.requests == []
    assert search_use_case.queries == []


@pytest.mark.asyncio
async def test_enhanced_search_pagination_reuses_cached_aggregate() -> None:
    use_case, agent_client, search_use_case = create_use_case(
        [
            assistant(tool_call("search_files", '{"query":"cat"}', "call-1")),
            assistant(
                tool_call(
                    "submit_selected_file_ids",
                    '{"file_ids":["file-1","file-2"]}',
                    "call-2",
                )
            ),
        ],
        [
            SearchResultsDTO(
                items=[
                    file_dto("file-1", "document", 0.8),
                    file_dto("file-2", "image", 0.9),
                ],
                counter={"document": 1, "image": 1, "video": 0},
                total=2,
            )
        ],
    )
    query = EnhancedSearchQuery(query="cat photos", folder_id=None, page_size=1)

    first_page = await use_case.execute(query)
    second_page = await use_case.execute(
        EnhancedSearchQuery(query="cat photos", folder_id=None, page_number=2, page_size=1)
    )

    assert [item.file_id for item in first_page.items] == ["file-2"]
    assert [item.file_id for item in second_page.items] == ["file-1"]
    assert first_page.total == second_page.total == 2
    assert len(agent_client.requests) == 2
    assert len(search_use_case.queries) == 1


@pytest.mark.asyncio
async def test_enhanced_search_sorting_reuses_cached_aggregate() -> None:
    use_case, agent_client, search_use_case = create_use_case(
        [
            assistant(tool_call("search_files", '{"query":"cat"}', "call-1")),
            assistant(
                tool_call(
                    "submit_selected_file_ids",
                    '{"file_ids":["file-1","file-2"]}',
                    "call-2",
                )
            ),
        ],
        [
            SearchResultsDTO(
                items=[
                    file_dto("file-1", "document", 0.8, size=20),
                    file_dto("file-2", "image", 0.9, size=10),
                ],
                counter={"document": 1, "image": 1, "video": 0},
                total=2,
            )
        ],
    )

    relevance_result = await use_case.execute(
        EnhancedSearchQuery(query="cat photos", folder_id=None, page_size=20)
    )
    size_result = await use_case.execute(
        EnhancedSearchQuery(
            query="cat photos",
            folder_id=None,
            page_size=20,
            sort_by=FileSortBy.SIZE,
            sort_order=SortOrder.DESC,
        )
    )

    assert [item.file_id for item in relevance_result.items] == ["file-2", "file-1"]
    assert [item.file_id for item in size_result.items] == ["file-1", "file-2"]
    assert len(agent_client.requests) == 2
    assert len(search_use_case.queries) == 1
