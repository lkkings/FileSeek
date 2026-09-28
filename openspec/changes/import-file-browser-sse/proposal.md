## Why

Folder cards currently expose placeholder import buttons, while the backend only supports synchronous single-file registration. Users need to choose multiple files from configured storage locations, start one import operation, and observe per-file progress without one failure stopping the rest of the batch.

## What Changes

- Replace the folder-card import placeholders with a real file import dialog.
- Use a dedicated import icon for importing files and remove the import-folder action.
- Let the dialog browse active storage locations through tabs.
- Support directory navigation, file selection, select all, and invert selection.
- Add backend directory browsing for local and mounted-NAS storage.
- **BREAKING**: Replace the single-file JSON import contract with a batch import session and SSE progress stream.
- Process batch items independently: one duplicate, unreadable, unsupported, or failed item records an item failure and processing continues.
- Report registration progress and task-processing progress through ordered SSE events.
- Keep an import session running when its SSE subscriber disconnects, and support reconnecting with `Last-Event-ID`.

## Capabilities

### New Capabilities

- `settings/storage-directory-browsing`: List directories and files from configured active storage locations with path containment and safe navigation.
- `library/import-file-browser`: Start a batch import into a folder, stream per-item and task progress over SSE, continue after item failures, and present the flow in the desktop import dialog.

### Modified Capabilities

- None.

## Impact

- Backend settings application and HTTP layers gain directory browsing.
- Backend library import gains batch use cases, import sessions, and SSE transport.
- Task progress becomes observable to import sessions without changing task persistence semantics.
- Desktop library UI, API services, i18n, and streaming transport are updated.
- Existing single-file API tests and frontend import service tests are migrated to the batch contract.
