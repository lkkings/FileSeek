## Context

Library folders are virtual groupings stored in `folders`; files point to one folder and one storage source. The existing batch import flow already validates the target folder, resolves the source file, copies it to a temporary path, creates a `files` record, and creates a queued task. Storage settings already define local and mounted NAS sources and provide directory browsing.

The new capability therefore adds persisted source bindings and a watcher orchestration layer rather than a second import pipeline.

## Goals / Non-Goals

**Goals:**

- Represent many watchable source directories per library folder.
- Reuse the existing add-file and task-queue semantics.
- Keep watcher state consistent through binding changes and backend restarts.
- Avoid duplicate imports and ambiguous folder assignment.
- Expose binding health without exposing storage credentials.
- Keep watcher I/O bounded so a burst of new files cannot overwhelm the event loop.

**Non-Goals:**

- Watching external HTTP/HTTPS sources or protocols that are not mounted as a filesystem.
- Supporting a file in multiple library folders.
- Moving, renaming, deleting, or reprocessing files when source files change.
- Providing cloud-storage change webhooks or server-side watch APIs.

## Decisions

### Data model

Create a `folder_source_bindings` table:

- `id`: stable binding identifier.
- `folder_id`: foreign key to `folders`, cascading on folder deletion.
- `storage_id`: storage source identifier, validated against active storage locations.
- `source_path`: canonical source-relative path for mounted sources or canonical absolute path for local sources.
- `recursive`: whether descendant directories are watched.
- `enabled`: user switch for watcher participation.
- `watch_status`: `watching`, `disabled`, `unavailable`, or `error`.
- `last_error` and `last_error_at`: latest user-readable watcher/import error.
- `created_at` and `updated_at`.

Add a unique constraint on `(folder_id, storage_id, source_path)`. New tables are created by the existing safe schema generation; no existing table needs an added column.

The storage identifier is stored as an identifier rather than a hard foreign key, matching `files.storage_id` and allowing the Settings feature to own storage deletion semantics. Deleting or deactivating a storage source causes bindings to become unavailable and stops their watchers.

### Source path semantics

Normalize paths before persistence:

- Local sources use canonical absolute paths.
- Mounted NAS sources use canonical paths relative to the configured mount root and reject `..`.
- Directory separators are normalized to `/`.

Only active `local` sources and active NAS sources using the `mounted` protocol are watchable. The binding use case resolves the directory through the storage source repository before saving, so invalid or unreadable directories are rejected at API time.

### Overlap handling

Before saving an active binding, compare it against all other active bindings for the same storage source. Reject bindings whose normalized path is equal to, an ancestor of, or a descendant of an existing binding. This applies even when both bindings target the same folder because nested active bindings produce duplicate events without adding user value.

The existing file model has one `folder_id` and a globally unique source path, so overlapping bindings across folders would otherwise create an ambiguous first-writer result. Validation keeps assignment deterministic.

### Watcher architecture

Add a backend `FolderSourceWatcherService` with one async watcher task per enabled binding. Each task:

1. Resolves the binding root through a source-root resolver.
2. Observes filesystem events under the root, including descendants when `recursive` is enabled.
3. Filters directories, hidden files, common partial-download files, and files already known to the watcher.
4. Waits until the candidate file exists and its size and modification time are unchanged across the configured number of consecutive settling intervals.
5. Calls the existing add-file use case with the binding's folder and resolved source path.
6. Marks successful and duplicate outcomes as processed.
7. Records failures in binding health and retries transient failures a bounded number of times.

Use `watchfiles` as the explicit backend dependency. It provides cross-platform filesystem event delivery for local paths and mounted filesystems; unmounted protocol clients would require polling or service-specific webhooks and remain out of scope.

### Event processing and concurrency

Each watcher task forwards candidates to a shared bounded import queue. A small worker pool, initially one worker, consumes the queue and executes the add-file use case. This prevents hundreds of simultaneous copy/hash operations from blocking the API event loop or creating an unbounded number of queued tasks.

The settling interval, number of consecutive stable checks, scan interval, and worker concurrency are backend settings with conservative defaults. The default settling interval is two seconds and files must remain unchanged for two consecutive checks; longer intervals can be configured for large network transfers. Unstable candidates are requeued after the settling interval rather than marked missing.

### Baseline and restart behavior

When a binding is first enabled, its watcher scans the watched directory and imports existing recognizable supported files through the same queue and `AddFileUseCase` path used for new events. Unsupported and unrecognized files do not create tasks. This makes the first binding useful immediately while keeping future arrivals and restart catch-up behavior consistent.

While the backend is running, new files are imported as events arrive. On backend restart, each enabled binding scans its root and compares files to its persisted seen set; unseen files that appeared while the backend was offline are imported. Successful, duplicate, unsupported, and failed paths are represented in binding-local seen state so restart scans do not repeatedly retry known outcomes.

While the backend remains running, a periodic scan task also reconciles enabled bindings and enqueues unseen paths. This compensates for missed filesystem events on local or mounted sources without waiting for a backend restart.

The seen-state store is keyed by binding, storage source, and canonical source path. It is deleted with the binding and does not alter library file records.

### API design

Expose nested folder resources:

- `GET /library/folders/{folder_id}/source-bindings`
- `POST /library/folders/{folder_id}/source-bindings`
- `PATCH /library/folders/{folder_id}/source-bindings/{binding_id}`
- `DELETE /library/folders/{folder_id}/source-bindings/{binding_id}`

Requests contain `storage_id`, `path`, `recursive`, and `enabled`. Responses contain normalized binding data, watch status, and recent error metadata; they never include storage account or credential fields.

The folder list response does not embed binding details. The folder details or folder settings area loads bindings separately to avoid increasing the cost of the main library query.

### Lifecycle integration

Start the watcher service after database initialization and task scheduler startup. On shutdown, stop watcher event intake and drain in-flight import operations before shutting down the task scheduler. This ordering prevents a watcher from creating a file or task after the scheduler has stopped.

Binding mutations notify the watcher service after the repository transaction succeeds. The service stops, replaces, or starts only the affected watcher task. Disabled bindings remain persisted but are not observed.

### Frontend interaction

In the Library folder management UI, add a source-binding section that:

- Lists bindings with source name, path, recursion, enabled state, and health.
- Reuses the storage directory browser to select a source directory.
- Allows enabling/disabling, recursive mode, and deletion.
- Shows the latest binding error and a retry action for recoverable watcher failures.

Folder creation remains unchanged; users add bindings after creating a folder.

## Risks / Trade-offs

- [Mounted network filesystems may not deliver reliable filesystem events] → The watcher performs periodic reconciliation scans; health state makes watcher failures visible.
- [A source directory may contain very many files] → Baseline scans use bounded concurrency and seen-state lookups; event imports use a bounded queue.
- [Adding explicit seen state increases storage] → The store only contains paths under opted-in bindings and is removed with the binding; the benefit is deterministic new-file behavior across restarts.
- [File settling can delay imports] → The delay is configurable and is preferable to importing partial files.
- [The current file model supports only one folder] → Overlapping active bindings are rejected, keeping assignment deterministic.
- [Watcher failures could be silent] → Watch status and last error are persisted and surfaced through the API and UI.

## Migration Plan

1. Add the new binding and seen-state models and let safe schema generation create their tables.
2. Deploy the API and watcher service; no existing rows require migration.
3. Users create bindings explicitly, which triggers the watcher's initial scan and import queue.
4. Rollback removes the feature and leaves existing imported files and tasks unchanged. The new tables can then be dropped manually if desired.
