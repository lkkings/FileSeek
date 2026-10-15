## Why

Resource-library folders currently require users to manually import files after those files arrive in a storage source. Users who organize incoming downloads, mounted NAS exports, or automation output into known directories must repeatedly perform the same import action.

This change lets a library folder watch one or more source directories and automatically register newly created supported files into that folder and the existing processing task queue.

## What Changes

- Add persisted folder source bindings: each library folder may bind multiple directories from multiple storage sources.
- Add backend APIs to list, create, update, enable/disable, and delete folder source bindings.
- Add a backend watcher service that observes enabled bindings, periodically scans for missed events, waits for newly created files to become stable, and imports them through the existing file registration flow.
- Automatically create a queued processing task for each successfully registered watched file.
- Start and stop watchers with the backend lifecycle and reconcile watcher state when bindings, folders, or storage sources change.
- Surface binding health and recent watcher/import errors in the folder management UI.
- Support filesystem-backed `local` sources and mounted NAS storage. External HTTP/HTTPS and unmounted network protocols remain unsupported for watching.
- Reject overlapping active bindings that would assign the same source file to multiple library folders.

## Capabilities

### New Capabilities
- `library/folder-source-watch-imports`: Requirements for binding library folders to storage source directories and automatically importing newly created files into the folder and task queue.

### Modified Capabilities

- None.

## Impact

- Backend database gains a folder-source binding table and startup schema management.
- Backend Library feature gains binding APIs and watcher orchestration.
- Backend startup/shutdown lifecycle starts and stops watcher sessions.
- Existing `AddFileUseCase` and task creation flow remain the import entry point.
- Settings storage source definitions and directory browsing are reused for source selection and path validation.
- Desktop Library folder UI gains binding management and health display.
- Backend dependency set gains an explicit filesystem watching dependency.
