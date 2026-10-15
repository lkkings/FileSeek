from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from collections.abc import AsyncGenerator, Callable
from dataclasses import asdict
from json import JSONDecodeError, loads
from typing import cast

from pydantic import ValidationError as PydanticValidationError

from fileseek.features.search.application.contracts import (
    AgentSearchRequest,
    SearchRequest,
    SelectedFileIdsRequest,
)
from fileseek.features.search.application.dto import (
    AgentAssistantMessage,
    AgentToolCall,
    EnhancedSearchProgressDTO,
    FileDTO,
    SearchResultsDTO,
)
from fileseek.features.search.application.enhanced_search_tools import (
    AGENT_SYSTEM_PROMPT,
    ENHANCED_SEARCH_TOOLS,
)
from fileseek.features.search.application.mappers import search_request_to_query
from fileseek.features.search.application.ports import (
    AgentCompletionClient,
    AgentConnection,
    AgentSettingsProvider,
)
from fileseek.features.search.application.queries import EnhancedSearchQuery
from fileseek.features.search.application.use_cases.search_files import SearchFilesUseCase
from fileseek.features.search.domain.exceptions import AgentProviderError
from fileseek.shared.domain.exceptions import ApplicationError, ValidationError
from fileseek.shared.utils.cache import TTLLRUCache

logger = logging.getLogger(__name__)

ENHANCED_SEARCH_CACHE_KEY = "enhanced_search"
AGENT_SEARCH_PAGE_NUMBER = 1
AGENT_SEARCH_PAGE_SIZE = 100

ProgressReporter = Callable[[EnhancedSearchProgressDTO], None]


class EnhancedSearchUseCase:
    def __init__(
        self,
        search_use_case: SearchFilesUseCase,
        agent_settings_provider: AgentSettingsProvider,
        agent_client_factory: Callable[[AgentConnection], AgentCompletionClient],
        cache: TTLLRUCache[str, tuple[FileDTO, ...]],
        *,
        max_tool_rounds: int = 8,
        max_file_ids: int = 100,
    ) -> None:
        self.search_use_case = search_use_case
        self.agent_settings_provider = agent_settings_provider
        self.agent_client_factory = agent_client_factory
        self.cache = cache
        self.max_tool_rounds = max_tool_rounds
        self.max_file_ids = max_file_ids

    async def execute(
        self,
        query: EnhancedSearchQuery,
        progress: ProgressReporter | None = None,
    ) -> SearchResultsDTO:
        natural_query = query.query.strip()
        if not natural_query:
            raise ValidationError("请输入搜索关键词")

        cache_key = self._cache_key(natural_query, query.folder_id, query.page_size)
        cached_items = await self.cache.get(ENHANCED_SEARCH_CACHE_KEY, cache_key)
        if cached_items is not None:
            self._report(
                progress,
                EnhancedSearchProgressDTO(
                    type="status",
                    phase="cache_hit",
                    message="正在返回缓存的检索结果",
                ),
            )
            return self._build_result(cached_items, query)

        connection = await self.agent_settings_provider.get()
        if connection is None:
            raise ValidationError("检索智能体未配置，请先完成系统设置")

        agent_client = self.agent_client_factory(connection)
        self._report(
            progress,
            EnhancedSearchProgressDTO(
                type="status",
                phase="starting",
                message="正在理解搜索意图",
            ),
        )
        verified_items = await self._run_agent(
            agent_client,
            natural_query,
            query.folder_id,
            progress,
        )
        await self.cache.set(ENHANCED_SEARCH_CACHE_KEY, cache_key, verified_items)
        self._report(
            progress,
            EnhancedSearchProgressDTO(
                type="status",
                phase="building_result",
                message="正在整理搜索结果",
            ),
        )
        return self._build_result(verified_items, query)

    async def execute_stream(
        self,
        query: EnhancedSearchQuery,
    ) -> AsyncGenerator[EnhancedSearchProgressDTO, None]:
        queue: asyncio.Queue[EnhancedSearchProgressDTO] = asyncio.Queue()
        runner = asyncio.create_task(self._execute_and_publish(query, queue))
        try:
            while True:
                event = await queue.get()
                yield event
                if event.type in {"result", "error"}:
                    return
        finally:
            if not runner.done():
                runner.cancel()
            await asyncio.gather(runner, return_exceptions=True)

    async def _execute_and_publish(
        self,
        query: EnhancedSearchQuery,
        queue: asyncio.Queue[EnhancedSearchProgressDTO],
    ) -> None:
        try:
            result = await self.execute(query, queue.put_nowait)
        except ApplicationError as exc:
            queue.put_nowait(EnhancedSearchProgressDTO(type="error", error=str(exc)))
            return
        except Exception:
            logger.exception("检索增强搜索流式执行失败")
            queue.put_nowait(EnhancedSearchProgressDTO(type="error", error="检索增强搜索失败"))
            return
        queue.put_nowait(EnhancedSearchProgressDTO(type="result", result=result))

    async def _run_agent(
        self,
        agent_client: AgentCompletionClient,
        natural_query: str,
        folder_id: str | None,
        progress: ProgressReporter | None = None,
    ) -> tuple[FileDTO, ...]:
        messages: list[dict[str, object]] = [
            {"role": "system", "content": AGENT_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps(
                    {"query": natural_query, "folder_id": folder_id},
                    ensure_ascii=False,
                ),
            },
        ]
        accumulated_items: dict[str, FileDTO] = {}

        for round_index in range(self.max_tool_rounds):
            round_number = round_index + 1
            self._report(
                progress,
                EnhancedSearchProgressDTO(
                    type="status",
                    phase="agent_round",
                    message=(
                        f"第 {round_number} 轮：正在理解搜索意图并制定检索计划"
                        if round_number == 1
                        else f"第 {round_number} 轮：正在分析检索结果并决定是否继续检索"
                    ),
                    round_number=round_number,
                ),
            )
            assistant = await agent_client.complete(messages, ENHANCED_SEARCH_TOOLS)
            messages.append(self._assistant_message(assistant))
            if assistant.content:
                self._report(
                    progress,
                    EnhancedSearchProgressDTO(
                        type="reasoning",
                        round_number=round_number,
                        content=assistant.content,
                    ),
                )
            if not assistant.tool_calls:
                raise AgentProviderError("Agent 未提交文件 ID")

            selected_ids: list[str] | None = None
            for tool_call in assistant.tool_calls:
                if tool_call.name == "submit_selected_file_ids":
                    self._report(
                        progress,
                        EnhancedSearchProgressDTO(
                            type="tool_call",
                            phase="submitting",
                            round_number=round_number,
                            tool_name=tool_call.name,
                            message="正在提交最终文件选择",
                        ),
                    )
                    selected_ids = self._parse_selected_ids(tool_call)
                    break
                if tool_call.name != "search_files":
                    raise AgentProviderError("Agent 调用了未知工具")
                agent_request = self._parse_search_request(tool_call)
                self._report(
                    progress,
                    EnhancedSearchProgressDTO(
                        type="tool_call",
                        phase="searching",
                        round_number=round_number,
                        tool_name=tool_call.name,
                        query=agent_request.query,
                        categories=tuple(agent_request.categories),
                        name_query=agent_request.name_query,
                    ),
                )
                result = await self._execute_search(tool_call, folder_id)
                self._accumulate_items(accumulated_items, result)
                self._report(
                    progress,
                    EnhancedSearchProgressDTO(
                        type="tool_result",
                        round_number=round_number,
                        tool_name=tool_call.name,
                        query=agent_request.query,
                        categories=tuple(agent_request.categories),
                        name_query=agent_request.name_query,
                        candidate_count=len(result.items),
                        total=result.total,
                    ),
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(
                            [{
                                "file_id": item.file_id,
                                "file_name": item.file_name,
                                "file_type": item.file_type,
                                "tags": item.tags,
                                "metadata": item.metadata,
                            } for item in result.items],
                            ensure_ascii=False,
                            default=str,
                        )[:2048],
                    }
                )

            if selected_ids is not None:
                self._report(
                    progress,
                    EnhancedSearchProgressDTO(
                        type="status",
                        phase="selecting",
                        message="正在筛选已验证的文件",
                        round_number=round_number,
                    ),
                )
                return tuple(
                    accumulated_items[file_id]
                    for file_id in selected_ids
                    if file_id in accumulated_items
                )

        raise AgentProviderError("Agent 工具调用次数超限")

    async def _execute_search(
        self,
        tool_call: AgentToolCall,
        folder_id: str | None,
    ) -> SearchResultsDTO:
        agent_request = self._parse_search_request(tool_call)
        request = SearchRequest(
            **agent_request.model_dump(),
            folder_id=folder_id,
            page_number=AGENT_SEARCH_PAGE_NUMBER,
            page_size=AGENT_SEARCH_PAGE_SIZE,
        )
        return await self.search_use_case.execute(search_request_to_query(request))

    def _parse_search_request(self, tool_call: AgentToolCall) -> AgentSearchRequest:
        try:
            arguments = cast("dict[str, object]", loads(tool_call.arguments))
            agent_request = AgentSearchRequest.model_validate(arguments)
        except (JSONDecodeError, PydanticValidationError, TypeError) as exc:
            raise AgentProviderError("Agent 搜索工具参数无效") from exc
        return agent_request

    def _parse_selected_ids(self, tool_call: AgentToolCall) -> list[str]:
        try:
            arguments = cast("dict[str, object]", loads(tool_call.arguments))
            request = SelectedFileIdsRequest.model_validate(arguments)
        except (JSONDecodeError, PydanticValidationError, TypeError) as exc:
            raise AgentProviderError("Agent 结果提交参数无效") from exc
        if len(request.file_ids) > self.max_file_ids:
            raise AgentProviderError("Agent 返回的文件 ID 数量超限")
        return request.file_ids

    @staticmethod
    def _accumulate_items(
        accumulated_items: dict[str, FileDTO],
        result: SearchResultsDTO,
    ) -> None:
        for item in result.items:
            current = accumulated_items.get(item.file_id)
            if current is None or item.score > current.score:
                accumulated_items[item.file_id] = item

    @staticmethod
    def _assistant_message(assistant: AgentAssistantMessage) -> dict[str, object]:
        message: dict[str, object] = {
            "role": "assistant",
            "content": assistant.content,
        }
        if assistant.tool_calls:
            message["tool_calls"] = [
                {
                    "id": tool_call.id,
                    "type": "function",
                    "function": {
                        "name": tool_call.name,
                        "arguments": tool_call.arguments,
                    },
                }
                for tool_call in assistant.tool_calls
            ]
        return message

    @staticmethod
    def _report(
        progress: ProgressReporter | None,
        event: EnhancedSearchProgressDTO,
    ) -> None:
        if progress is not None:
            progress(event)

    @staticmethod
    def _build_result(
        items: tuple[FileDTO, ...],
        query: EnhancedSearchQuery,
    ) -> SearchResultsDTO:
        ordered_items = list(items)
        reverse = query.sort_order.value == "desc"
        if query.sort_by.value == "relevance":
            ordered_items.sort(key=lambda item: item.score, reverse=reverse)
        elif query.sort_by.value == "created_at":
            ordered_items.sort(
                key=lambda item: item.modified or "",
                reverse=reverse,
            )
        else:
            ordered_items.sort(key=lambda item: item.size or 0, reverse=reverse)

        counter = {"document": 0, "image": 0, "video": 0}
        for item in ordered_items:
            counter[item.category] = counter.get(item.category, 0) + 1

        start = (query.page_number - 1) * query.page_size
        end = start + query.page_size
        return SearchResultsDTO(
            items=ordered_items[start:end],
            counter=counter,
            total=len(ordered_items),
            page_number=query.page_number,
            page_size=query.page_size,
        )

    @staticmethod
    def _cache_key(query: str, folder_id: str | None, page_size: int) -> str:
        payload = json.dumps(
            {"query": query, "folder_id": folder_id, "page_size": page_size},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
