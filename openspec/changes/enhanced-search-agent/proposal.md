## Why

FileSeek currently maps a natural-language query to one semantic search, which can miss results that require multiple query formulations or filtering strategies. Users also need a guided path from a search-mode switch to the external agent configuration required for that workflow.

## What Changes

- Add a **启动检索增强** toggle to the search bar; it defaults to off.
- Show the existing advanced-filter controls only while retrieval augmentation is off.
- Add system settings for an OpenAI-compatible retrieval agent, including `base_url` and locally stored `api_key`.
- Add an Agent connection test so users can verify the current settings before use.
- Add an enhanced-search backend flow that sends the user's natural-language request to a retrieval expert agent.
- Expose the search/filter parameters as the agent's `search_files` tool, excluding `folder_id`, pagination, and sorting; allow multiple tool calls.
- Filter final results by agent-selected `file_id` values that actually appeared in tool results; never trust generated file records.
- Aggregate selected results and return the existing search response structure with existing pagination behavior.
- Reuse one short-lived backend aggregation result across pagination requests so page changes do not re-run the external agent.

## Capabilities

### New Capabilities
- `enhanced-search`: Search-mode selection, agent configuration requirements, multi-turn retrieval-agent tool use, ID-only result filtering, aggregation, pagination, and response compatibility.

### Modified Capabilities
- None. No existing OpenSpec capability currently describes search.

## Impact

- **Desktop**: Library search bar, search state hook, settings UI, settings API client, and related tests.
- **Backend**: Settings feature storage/API, search feature, agent client, dependency wiring, database schema, and API tests.
- **API**: New agent settings endpoints, new enhanced-search endpoint, and a short-lived server-side aggregation cache.
- **Dependencies**: Add or use an HTTP client suitable for OpenAI-compatible Chat Completions and tool calling.
