## 1. Backend Progress Contract

- [x] 1.1 Define progress event DTOs and serialization helpers; verify unit tests cover status, reasoning, tool call, tool result, result, and error event shapes.
- [x] 1.2 Refactor enhanced-search orchestration to emit validated round-level progress while preserving the existing use-case result; verify enhanced-search use-case tests prove unchanged filtering, aggregation, sorting, counters, pagination, and caching.
- [x] 1.3 Add `POST /search/enhanced/stream` with SSE formatting, keep-alive comments, terminal result/error events, and the unchanged non-streaming endpoint; verify API tests cover multi-tool streams, cache hits, errors, and compatibility.
- [x] 1.4 Verify progress payloads never contain API keys, raw provider JSON, internal chat messages, or hidden reasoning through focused payload-redaction tests.

## 2. Desktop Stream Client and State

- [x] 2.1 Implement the browser enhanced-search stream transport and SSE parser; verify unit tests cover chunk boundaries, terminal events, malformed blocks, and abort signals.
- [x] 2.2 Extend search state so initial enhanced searches consume the stream, advanced searches retain the mutation path, and final events populate the existing search result state; verify hook tests cover both paths.
- [x] 2.3 Add request-sequence and unmount guards plus cancellation of superseded streams; verify hook tests prove late events cannot overwrite a newer search and unmount closes the stream.
- [x] 2.4 Keep pagination and sorting on the existing enhanced endpoint after stream completion; verify hook tests prove page and sort changes do not reopen the progress stream while cached.

## 3. Tauri Transport

- [x] 3.1 Add the scoped search progress stream command with POST support, backend token handling, dedicated chunk events, and cancellation registry; verify Rust unit tests cover path validation, token non-exposure, and cancellation behavior.
- [x] 3.2 Add the TypeScript Tauri transport and runtime selection; verify unit tests prove browser and Tauri modes choose the expected transport and chunks reach the shared parser.
- [x] 3.3 Register the command and verify packaged-runtime wiring through focused configuration or command registration tests.

## 4. Progress UI and Localization

- [x] 4.1 Implement the running retrieval timeline with distinct reasoning, tool, outcome, and terminal states; verify component tests cover multiple rounds, user-friendly tool summaries, and no raw JSON.
- [x] 4.2 Replace the primary loading timeline with the existing results view on the final event and provide a collapsed completed-process disclosure; verify component tests cover non-empty, empty, and error result transitions.
- [x] 4.3 Add Chinese and English localization for all progress states and errors; verify locale snapshot or text tests cover every user-facing key.

## 5. Integration Validation

- [x] 5.1 Run backend formatting, type checks, and focused search/API tests; verify all required suites pass.
- [x] 5.2 Run desktop type checking, lint, and focused file-search/Tauri transport tests; verify all required suites pass.
- [x] 5.3 Run strict OpenSpec validation and review implementation against every scenario in `enhanced-search-progress/spec.md`; record the final verification result.
