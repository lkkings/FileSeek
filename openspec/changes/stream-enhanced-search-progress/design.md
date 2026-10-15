## Context

The existing enhanced-search flow runs the entire agent loop in `EnhancedSearchUseCase` and returns a single `SearchResultsDTO`. The desktop hook uses a React Query mutation, and `SearchResultsView` renders only a generic loading message until that response arrives. The project already has browser and Tauri SSE patterns for import progress.

## Goals / Non-Goals

**Goals:**
- Expose round-level progress from the existing agent loop without changing final result semantics.
- Render progress in language users can understand.
- Reuse the current search results UI after completion.
- Keep the existing endpoint and cached pagination/sorting path intact.
- Work in browser development mode and packaged Tauri mode.

**Non-Goals:**
- Token-by-token streaming of model output.
- Exposing hidden chain-of-thought, raw provider responses, or full internal message arrays.
- Changing normal advanced search behavior.
- Introducing a job queue or persistent progress history.

## Decisions

### Round-level SSE

Add `POST /api/v1/search/enhanced/stream` returning `text/event-stream`. Use round-level events rather than Chat Completions token deltas. The current agent client already returns complete assistant messages and tool calls, so this provides useful progress with far less provider-specific delta aggregation. If finer-grained model output is wanted later, it can be layered onto the same event contract.

Use one JSON progress event type with a discriminated `type`, rather than separate SSE event names, so the frontend parser and tests can validate one stable schema:

```text
status    -> phase and user-facing message
reasoning -> round and visible assistant summary
tool_call -> round, tool identity, and user-facing summary
tool_result -> round, tool identity, outcome, and candidate count
result    -> existing enhanced-search response payload
error     -> terminal user-facing error
```

The `result` and `error` events are terminal. The SSE generator also sends periodic comments to keep proxies and connections alive.

### Reuse the agent loop

Refactor the enhanced-search execution path so one orchestration implementation can report events while preserving the existing `execute` behavior. A stream-capable path will emit each phase before and after it occurs. The non-streaming endpoint can ignore progress events and return the final result. This avoids duplicate agent-loop logic and prevents progress behavior from changing ID verification, aggregation, sorting, counters, or pagination.

Progress must summarize only user-safe assistant `content`, recognized tool names, and parsed tool outcomes. It must not forward provider JSON, internal chat messages, API keys, or hidden reasoning.

### Frontend stream state

For the initial enhanced search, bypass the React Query mutation and use a dedicated stream API client. Maintain the current advanced-search mutation unchanged. The enhanced state holds:

- stream status
- ordered progress events
- final result payload
- terminal error
- active stream handle

Starting a new search aborts the old handle, clears progress, and tags state updates with the current request sequence so a late event cannot overwrite a newer search. Unmounting the hook closes the active stream.

The final `result` event is stored in the same search result state shape consumed by `SearchResultsView`. On completion, the UI stops treating the search as loading and renders the existing file rows, sort controls, pagination, counters, and detail interactions. The completed process is available behind a collapsed disclosure.

### Browser and Tauri transports

Use `fetch` with `POST`, `Accept: text/event-stream`, and an `AbortSignal` in browser mode. Reuse the existing SSE block parser shape, but define a search-progress parser instead of coupling enhanced search to import event types.

For packaged Tauri mode, add a narrowly scoped search progress stream command. The command sends the approved backend token, POSTs the exact enhanced-search request, emits chunks to a dedicated Tauri event, and supports cancellation through a stream-id registry. Restrict the allowed path to `/api/v1/search/enhanced/stream`; reject query strings, path traversal, and other paths. The emitted payload must not include the backend token.

### Pagination and compatibility

Only the initial enhanced search uses the streaming endpoint. Page and sort changes continue through the existing `POST /search/enhanced`. The existing aggregate cache remains authoritative. A cache hit can emit a brief status event followed by the final result event, avoiding the appearance of a fake agent run.

## Risks / Trade-offs

- [Provider progress granularity] -> Round-level events may have pauses between agent calls; status and SSE keep-alive events make those pauses visible without implying token streaming.
- [Tauri cancellation] -> A blocking reader can outlive frontend listeners; maintain a stream-id cancellation registry and stop emitting or reading as soon as cancellation is observed.
- [Late events race] -> Request sequence guards prevent an aborted or superseded stream from updating newer search state.
- [Sensitive data leakage] -> Construct progress payloads from validated, whitelisted fields only; never forward raw provider or tool JSON.
- [SSE parser divergence] -> Share the SSE block parsing shape and test browser, Tauri, reconnect-free search, and malformed-block behavior.
- [Error visibility] -> Every failure path emits one terminal error event, and UI copy distinguishes provider, configuration, and validation failures where possible.

## Migration Plan

1. Add backend progress event schemas and the streaming endpoint without changing the existing endpoint.
2. Extract stream events from the current enhanced-search orchestration path.
3. Add the browser stream client and frontend progress state.
4. Add the Tauri transport command and wire runtime selection.
5. Render the progress timeline and final result through the existing results view.
6. Validate compatibility, cancellation, errors, and cached pagination.
7. Rollback by routing the UI back to the non-streaming endpoint and leaving the new endpoint unused.
