## 1. Storage Directory Browsing

- [x] 1.1 Add storage-directory query, DTO, use case, and unsupported-storage error mapping; verify unit tests cover local, mounted NAS, deleted, and unsupported protocol requests.
- [x] 1.2 Implement the filesystem directory adapter with root containment, traversal rejection, symlink-escape rejection, deterministic sorting, and entry metadata; verify adapter tests cover every safety case.
- [x] 1.3 Add settings HTTP schemas, mapper, route, and dependency registration; verify API tests cover successful browsing, missing directories, and unavailable storage.

## 2. Batch Import Session

- [x] 2.1 Refactor file registration to return both file and task identifiers; verify use-case tests preserve source-index behavior and expose both identifiers.
- [x] 2.2 Add batch import command, result DTO, and sequential runner; verify unit tests continue after duplicate, missing, unsupported, and processing failures.
- [x] 2.3 Implement the in-memory import session manager with ordered event IDs, buffered history, live subscribers, disconnect tolerance, and bounded session cleanup; verify manager tests cover reconnection and completion replay.
- [x] 2.4 Add the task snapshot port and bootstrap adapter backed by the existing task repository; verify tests emit changed progress and terminal states without altering scheduler persistence.
- [x] 2.5 Add batch import request/response schemas and the `POST /library/files/import` route; verify API tests reject empty batches and missing folders before creating a session.
- [x] 2.6 Add the SSE events route with ordered event IDs, JSON payloads, heartbeat comments, no-cache headers, and `Last-Event-ID` replay; verify API tests parse the stream and resume after disconnect.
- [x] 2.7 Remove the single-file import route and migrate its tests to the batch contract; verify no obsolete single-file route remains in the OpenAPI surface.

## 3. Desktop API and Streaming Transport

- [x] 3.1 Add typed frontend services for starting a batch import and listing storage directories; verify service tests assert request paths and payload field names.
- [x] 3.2 Implement the browser SSE client and event parser with automatic reconnection and terminal event handling; verify tests cover chunk parsing, `Last-Event-ID`, failures, and completion.
- [x] 3.3 Add the packaged-Tauri SSE bridge that opens the backend stream with the token and forwards chunks to the WebView; verify Rust tests confirm the token remains outside JavaScript-facing payloads.
- [x] 3.4 Register the streaming transport in the desktop service layer without changing existing JSON client behavior; verify typecheck and existing API-client tests pass.

## 4. Import Dialog UI

- [x] 4.1 Build the storage tab and directory list with loading, empty, error, retry, and navigation states; verify component tests cover tab switching and directory clicks.
- [x] 4.2 Implement file selection state keyed by storage and source path, select all, and invert selection; verify component tests confirm selections persist across navigation.
- [x] 4.3 Build the batch progress view for queued, registered, processing, failed, and completed items; verify component tests render item failures without stopping later progress.
- [x] 4.4 Wire the import dialog into the library page and folder-card import action, replace the import icon, and remove the import-folder button; verify component tests cover opening and closing the dialog.
- [x] 4.5 Add all dialog labels and accessibility attributes through the i18n layer; verify English and Chinese strings and keyboard/aria behavior in component tests.

## 5. Integration and Validation

- [x] 5.1 Add a backend integration test that imports a mixed batch where one item fails and later items succeed; verify the SSE stream records the failure and still completes the remaining items.
- [x] 5.2 Add a frontend integration test that browses storage, selects files, starts import, and renders streamed progress; verify user interaction and API mocks cover the complete flow.
- [x] 5.3 Run targeted backend tests for settings, library, tasks, and SSE transport; verify all relevant suites pass.
- [x] 5.4 Run desktop tests, typecheck, and lint; verify no regressions in existing library and API-client behavior.
- [ ] 5.5 Verify the flow manually in browser development and packaged Tauri; confirm SSE progress, reconnect behavior, and token isolation.

## 6. Explorer Path Navigation

- [x] 6.1 Return the resolved current path, default empty system-local requests to the OS user home, and support parent and pasted-path navigation; verify backend and component tests cover default, parent, and direct paths.
- [x] 6.2 Allow the local storage location to browse readable paths outside its configured `root_path`; verify backend tests cover a pasted path outside the configured root while mounted-NAS containment remains enforced.
- [x] 6.3 Filter directory file entries by filename suffix so only supported document, image, and video files are returned; verify backend tests omit unsupported files while retaining directories.
