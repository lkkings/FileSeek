## 1. Agent Settings

- [x] 1.1 Add the agent settings database model, domain entity, DTOs, repository, and dependency wiring; verify unit/API tests prove settings persist and a missing key is preserved when omitted.
- [x] 1.2 Implement `GET /settings/agent` and `PUT /settings/agent` with validation and masked key behavior; verify API tests cover save, read, incomplete configuration, and invalid URLs.
- [x] 1.3 Add the desktop settings API client and agent configuration card; verify component tests cover loading, saving, masked key display, and incomplete-state guidance.

## 2. Agent Orchestration

- [x] 2.1 Add the OpenAI-compatible Chat Completions client with tool calling, timeout, response validation, and redacted errors; verify client unit tests with fake HTTP responses.
- [x] 2.2 Implement the enhanced-search use case and agent loop that executes `search_files`, accumulates real `FileItem` records, verifies submitted IDs, and rejects malformed tool calls; verify use-case tests with a scripted fake agent.
- [x] 2.3 Implement verified-result aggregation, sorting, counters, pagination, and the TTL/LRU cache; verify pagination and sorting tests prove page changes do not re-run the agent while cached.
- [x] 2.4 Add `POST /search/enhanced`, dependency wiring, and request/response schemas; verify API tests cover missing settings, successful aggregation, empty results, and provider failures.

## 3. Search UI

- [x] 3.1 Extend search state with Advanced Filters/Retrieval Augmented mode and endpoint selection; verify hook tests cover mode routing and configuration-gated submission.
- [x] 3.2 Add the search-bar mode selector and hide Advanced Filters outside Advanced Filters mode; verify component tests cover both mode transitions.
- [x] 3.3 Integrate enhanced mode with the library page, inline settings guidance, pagination, and sorting; verify integration tests cover successful search, unconfigured search, and page/sort changes.

## 4. Validation

- [x] 4.1 Run backend formatting, type checks, and the focused settings/search test suites; verify all new and existing related tests pass.
- [x] 4.2 Run desktop type checking, lint, and focused search/settings tests; verify all new and existing related tests pass.
- [x] 4.3 Run strict OpenSpec validation and review the implementation against the spec scenarios; verify the change is ready to apply.

## 5. Follow-up Refinements

- [x] 5.1 Remove `folder_id`, pagination, and sorting from the agent search tool schema; inject the frontend-supplied folder scope during backend execution.
- [x] 5.2 Replace the two-option search mode selector with a single **启动检索增强** toggle and resize the advanced-filter button.
- [x] 5.3 Add an Agent settings connection test that reuses a stored key when omitted, reports provider failures safely, and verifies the desktop settings interaction.
- [x] 5.4 Show a full search loading state that disables controls and prevents duplicate submissions; add actionable 401 guidance and document the Tauri backend log location.
- [x] 5.5 Forward backend logs to the `tauri dev` terminal and add `npm run backend:log` for direct log streaming.
