## Context

The existing library search already provides semantic search, advanced filters, pagination, and a stable response envelope. There is no stored configuration for an external OpenAI-compatible agent, and the desktop does not call external model providers directly. The enhanced flow must reuse the current search contract while adding an agent-driven planning and selection layer.

## Goals / Non-Goals

**Goals:**
- Keep the agent API key in the local backend and never send it to the desktop renderer.
- Reuse the existing search request and response contracts.
- Support multiple agent-initiated searches and ID-only final selection.
- Reuse existing frontend pagination and sorting controls over an aggregated result set.
- Provide clear user guidance when agent settings are incomplete.

**Non-Goals:**
- Do not replace the existing advanced-filter search path.
- Do not let the agent generate or mutate file records.
- Do not add autonomous file operations; the agent gets one read-only search tool.
- Do not implement streaming agent progress or conversation history.

## Decisions

### Backend orchestration

Add `POST /search/enhanced` in the search feature and keep all external provider calls in the backend. The desktop calls only the local API.

This avoids exposing the API key to the renderer, keeps provider-specific handling out of React, and lets the backend validate tool arguments before executing searches. A frontend-direct provider integration would reduce backend coupling but would leak the credential and duplicate response/tool handling.

### Agent settings model

Add a singleton agent-settings database model and repository in the settings feature with:

- `base_url`
- `api_key`
- `model`
- timestamps

Expose `GET /settings/agent` and `PUT /settings/agent`. The read response includes the base URL, model, and an `api_key_configured` boolean, but not the full key. The update request accepts a new key; an omitted or `null` key preserves the stored key so users can change the URL or model without retyping the secret.

Expose `POST /settings/agent/test`. The request follows the update settings contract, but a missing key falls back to the stored key and no settings are persisted. The backend performs one minimal OpenAI-compatible Chat Completions request and returns a `{success, message}` result. Provider failures are returned as failed test results with actionable messages and never include the API key.

The design intentionally adds `model` beyond the user-mentioned `base_url` and `api_key` because Chat Completions requests require a model identifier. Enhanced search is considered ready only when all three fields are present.

Store the key in the existing local database rather than the macOS Keychain. This follows the product's current local backend persistence model and keeps the change cross-platform, but it means the database must continue to be treated as local credential-bearing data.

### OpenAI-compatible client

Use the Chat Completions tool-calling protocol with `httpx` as a runtime dependency rather than adding a provider SDK.

The request uses:

- `base_url + /chat/completions`
- Bearer authentication with the stored API key
- the stored model
- a retrieval-expert system prompt
- two tools: `search_files` and `submit_selected_file_ids`

The `search_files` JSON schema is generated from a dedicated agent request model aligned with the search API's query and filter fields. It intentionally excludes `folder_id`, pagination, and sorting: the enhanced-search request supplies the folder scope, and result pagination/sorting belong to the user-facing aggregate. The final-selection tool returns only IDs, which is stronger than parsing free text and prevents the provider from supplying generated fields.

Bound the loop with a maximum number of tool rounds, an overall timeout, and a maximum final ID count. Reject malformed or unknown tool calls and stop the search rather than guessing the agent's intent.

### Tool execution and result verification

For each `search_files` call:

1. Validate arguments against the agent search request model.
2. Inject the enhanced-search request's `folder_id` and fixed internal result defaults.
3. Execute the existing search use case.
4. Return the normal search payload to the agent.
5. Accumulate every returned `FileItem` in an ID-keyed map.

When duplicate IDs appear across searches, keep the item and use the highest score seen for that ID. Final agent-submitted IDs are intersected with that accumulated map. Unverified IDs are silently dropped; if no verified IDs remain, return a successful empty search response because the agent did not find matching indexed files. The agent's prose is never used as result data.

### Aggregation, sorting, and pagination

Compute the final list from verified accumulated items. Apply the requested sort locally, then paginate. Return the existing fields:

- `items`
- `total`
- `page_number`
- `page_size`
- `has_more`
- `counter`

`total` and `counter` are based on the complete verified set, not only the current page.

Keep a small in-memory TTL cache of the verified aggregate, keyed by the natural-language query, search scope, and page size. Exclude page number and sort fields so:

- page navigation reads the same aggregate
- sorting changes can re-sort the same aggregate
- changing query or folder scope creates a new aggregate

Use an LRU bound and a short TTL to limit stale results and memory use. Because this is a local single-user backend, an in-memory cache is simpler and avoids extending the response contract with a cache token. A persistent cache would survive restarts but would add schema and invalidation complexity without improving the immediate pagination experience.

If a cache entry is absent or expired, rerun the agent for that page request.

### Frontend mode handling

Extend the search bar with one **启动检索增强** toggle, defaulting to off. The advanced-filter affordance is rendered only while the toggle is off and is sized consistently with the search bar.

Add an agent settings query and a settings card for base URL, model, and API key. Before submitting in Retrieval Augmented mode, the frontend checks the configuration status and shows an inline action linking to system settings if incomplete. The backend still rejects incomplete configuration so API callers receive the same guard.

The existing search hook chooses the local endpoint based on mode. Sorting and pagination continue to call the enhanced endpoint with the current query and scope while the mode remains Retrieval Augmented.

## Risks / Trade-offs

- [External latency and cost] -> Cap tool rounds, cap result size, set request timeouts, and cache the aggregate for pagination.
- [Provider incompatibility] -> Validate Chat Completions/tool-call response shapes and return a clear provider error; keep provider logic isolated behind one port.
- [Secret exposure] -> Never return the full key, redact logs, and keep the key in request bodies/headers only.
- [Agent hallucination] -> Accept only IDs seen in actual tool results and reconstruct all fields from accumulated tool output.
- [Stale cached results] -> Use short TTL and scope-aware cache keys; new files become visible after expiry or a new query.
- [Large result sets] -> Limit final IDs and page size, and use an LRU aggregate cache.

## Migration Plan

1. Add the agent settings table with no default configuration.
2. Register settings and enhanced-search endpoints.
3. Roll out the frontend mode selector and settings card.
4. Users opt in by saving agent settings; the existing search path remains unchanged.
5. Rollback by hiding Retrieval Augmented mode and leaving the new settings row unused.
