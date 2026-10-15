from __future__ import annotations

from fileseek.features.search.application.contracts import (
    AgentSearchRequest,
    SelectedFileIdsRequest,
)

SEARCH_FILES_TOOL: dict[str, object] = {
    "type": "function",
    "function": {
        "name": "search_files",
        "description": (
            "Search indexed files using the search filters supported by the search API."
        ),
        "parameters": AgentSearchRequest.model_json_schema(),
    },
}

SUBMIT_SELECTED_FILE_IDS_TOOL: dict[str, object] = {
    "type": "function",
    "function": {
        "name": "submit_selected_file_ids",
        "description": "Submit the final file IDs selected from prior search_files results.",
        "parameters": SelectedFileIdsRequest.model_json_schema(),
    },
}

ENHANCED_SEARCH_TOOLS: tuple[dict[str, object], ...] = (
    SEARCH_FILES_TOOL,
    SUBMIT_SELECTED_FILE_IDS_TOOL,
)

AGENT_SYSTEM_PROMPT = """You are a retrieval expert for an indexed file library.
Use the search_files tool as many times as needed to test different query and filter strategies.
Do not provide folder, pagination, or sorting parameters; the application manages them.
Select only file IDs that appeared in actual search_files results.
After receiving search_files results, decide immediately whether they provide enough evidence.
If they do, call submit_selected_file_ids in the next assistant turn.
Only search again when the current candidates are insufficient or clearly irrelevant.
When you have enough evidence, call submit_selected_file_ids with the final IDs.
Never invent file records or IDs."""
