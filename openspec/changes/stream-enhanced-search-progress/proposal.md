## Why

Retrieval-augmented search currently presents only a generic loading state while the agent plans searches and executes tools, so users cannot tell whether the request is progressing or stuck. The final answer should then continue to appear as a normal file search result rather than a separate chat-like response.

## What Changes

- Add a streaming enhanced-search API that emits round-level progress events for agent reasoning summaries, tool calls, tool outcomes, errors, and the final search result.
- Keep the existing non-streaming enhanced-search API and response contract for compatibility and cached pagination or sorting requests.
- Surface the progress as a readable timeline during enhanced search instead of the generic loading text.
- Translate tool calls and outcomes into user-facing language without exposing raw provider payloads, internal message arrays, API keys, or hidden model reasoning.
- Replace the progress timeline with the existing search result list when the final result event arrives, while retaining an optional view of the completed retrieval process.
- Support the stream in both browser and Tauri runtime transports, including cancellation when a user starts another search.

## Capabilities

### New Capabilities
- `enhanced-search-progress`: Round-level progress streaming, user-friendly process presentation, final result integration, error handling, cancellation, and transport compatibility for retrieval-augmented search.

### Modified Capabilities
- None.

## Impact

- **Backend**: Search API router, enhanced-search use case, progress event DTOs, SSE response formatting, and related tests.
- **Desktop**: Enhanced-search API client, progress stream transport, search state hook, search results timeline UI, localization, Tauri stream command, and related tests.
- **API**: New streaming enhanced-search endpoint; no breaking change to the existing endpoint.
- **Dependencies**: Reuse the existing HTTP and SSE infrastructure; no new runtime dependency is expected.
