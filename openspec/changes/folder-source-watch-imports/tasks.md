## 1. Foundation

- [x] 1.1 Add `watchfiles` as an explicit backend dependency and add watcher settling/concurrency settings; verify dependency resolution and settings tests pass.
- [x] 1.2 Add folder source binding and binding seen-state database models with canonical field constraints; verify model/repository tests cover persistence and cascade behavior.
- [x] 1.3 Define folder source binding domain entities, repository ports, and mappers; verify unit tests cover status transitions and normalized response data.

## 2. Binding Use Cases

- [x] 2.1 Implement source path normalization and watchability validation for local and mounted NAS sources; verify unit tests cover absolute paths, relative mounted paths, `..` rejection, and unsupported protocols.
- [x] 2.2 Implement binding overlap validation across active bindings; verify unit tests reject equal, ancestor, and descendant overlaps without modifying existing bindings.
- [x] 2.3 Implement list, create, update, enable/disable, and delete use cases; verify use-case tests cover success paths, validation errors, missing folder/storage, and health metadata updates.
- [x] 2.4 Implement initial binding scans that import existing recognizable supported files; verify tests confirm historical supported files are registered and queued.
- [x] 2.5 Implement a source-root resolver port and storage-backed adapter; verify tests confirm local roots, mounted roots, and unavailable roots are handled correctly.

## 3. Watcher Service

- [x] 3.1 Implement the watcher service lifecycle, per-binding tasks, and graceful cancellation; verify tests confirm watchers start, stop, and do not leak tasks after disable/delete.
- [x] 3.2 Implement filesystem event filtering for directories, hidden files, partial-download files, duplicate events, and non-recursive bindings; verify unit tests cover each filter behavior.
- [x] 3.3 Implement stable-file detection using size and modification time; verify tests cover delayed imports, changed files, and files removed before processing.
- [x] 3.4 Implement a bounded shared import queue and worker that reuses `AddFileUseCase`; verify tests show one queued task per new file and no duplicate task for repeated events.
- [x] 3.5 Implement bounded transient failure retries and persistent binding health updates; verify tests record recoverable and terminal import errors.
- [x] 3.6 Implement restart and offline catch-up scans using binding seen state; verify tests import files created while the backend was offline and skip already-seen files.
- [x] 3.7 Implement binding change reconciliation; verify tests dynamically start, stop, or replace only the affected watcher.
- [x] 3.8 Implement periodic binding scans and consecutive stability checks; verify tests cover missed filesystem events, delayed imports, and paused writers.

## 4. HTTP API

- [x] 4.1 Add Pydantic schemas and mappers for binding requests and responses; verify serialization tests hide credentials and emit snake_case API fields.
- [x] 4.2 Add nested folder binding routes and dependency wiring; verify API tests cover CRUD, validation, overlap, and health responses.
- [x] 4.3 Add router-level error handling for unavailable folders, storage, and watcher conflicts; verify API tests return stable user-readable errors.

## 5. Backend Lifecycle Integration

- [x] 5.1 Build and register the watcher service in the application container; verify startup creates a single service instance and shutdown cancels watcher tasks.
- [x] 5.2 Integrate watcher startup after database and scheduler initialization and shutdown before scheduler shutdown; verify lifespan tests confirm ordering and no post-shutdown task creation.
- [x] 5.3 Stop or mark bindings unavailable when folders or storage sources change; verify integration tests cover folder deletion, storage deletion, and storage status changes.

## 6. Desktop UI

- [x] 6.1 Add typed API client functions for folder source bindings; verify frontend service tests cover request paths and payload conversion.
- [x] 6.2 Add a React Query hook for binding listing and mutations; verify hook tests cover loading, optimistic invalidation, errors, and retry.
- [x] 6.3 Add folder binding management UI using the existing storage directory browser; verify component tests cover selecting multiple sources, recursive mode, enable/disable, and delete.
- [x] 6.4 Add binding health and recent-error display; verify component tests render watching, disabled, unavailable, and error states without credentials.
- [x] 6.5 Add localized strings for binding management and health states; verify locale coverage for zh-CN and en-US.

## 7. Verification

- [x] 7.1 Add backend watcher integration tests for local file creation and queued task creation; verify tests exercise real filesystem events without depending on timing-sensitive sleeps.
- [ ] 7.2 Run backend formatting, lint, type checking, and tests; verify the configured backend quality commands pass.
- [ ] 7.3 Run desktop type checking, lint, and tests; verify the configured desktop quality commands pass.
- [ ] 7.4 Manually verify end-to-end behavior with one local binding and one mounted binding; confirm historical supported files are imported, new files are imported into the bound folder, tasks appear as queued, and app restart imports offline arrivals.
