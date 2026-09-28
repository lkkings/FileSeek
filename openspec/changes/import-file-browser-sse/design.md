## Context

The library already has a single-file registration use case, active storage locations, a task scheduler with persisted progress, and a JSON-only desktop API client. Folder-card import buttons are placeholders. See `proposal.md` for the product motivation and `specs/` for the behavior contract.

## Goals / Non-Goals

**Goals:**

- Keep directory browsing and batch import behind application ports so HTTP and UI remain thin.
- Make import sessions independent of SSE subscriber lifetime.
- Reuse the existing task scheduler and persisted task progress.
- Preserve the existing source-indexing model: imports register original source files and do not copy them into the library root.
- Keep the backend token out of WebView JavaScript in packaged Tauri builds.

**Non-Goals:**

- Implementing direct SMB, NFS, WebDAV, HTTP, or HTTPS directory browsing.
- Adding a new task queue or replacing the current scheduler.
- Persisting import sessions across backend restarts.
- Copying, moving, or deduplicating source files.
- Supporting folder imports in this change.

## Decisions

### Split batch start and SSE subscription

Use:

- `POST /api/v1/library/files/import` to validate the request, create a session, and return `{ import_id, total }`.
- `GET /api/v1/library/files/import/{import_id}/events` to subscribe to SSE.

This is preferable to a POST that directly streams SSE:

- Standard `EventSource` clients can use the GET stream.
- Disconnecting the browser tab or dialog does not need to cancel background import work.
- `Last-Event-ID` reconnect semantics remain straightforward.
- Request validation can still return normal JSON errors before a stream starts.

### Keep sessions in memory

Create an `ImportSessionManager` singleton in application state:

- It owns a background import task.
- It stores an ordered event history with monotonically increasing event IDs.
- It buffers events long enough for reconnect and late subscribers.
- It publishes live events to subscriber queues.

Sessions are intentionally not persisted. The task records they create remain in the existing task tables, so a backend restart can continue queued work even though the import progress stream is no longer resumable. This avoids a schema migration for a short-lived UI session.

### Process items sequentially

The batch runner imports files one at a time:

1. Emit `item_started`.
2. Register the source file and create its task.
3. Emit `item_registered`.
4. Track task progress until terminal state.
5. Emit `item_completed` or `item_failed`.
6. Continue to the next item.

Sequential processing gives deterministic progress and avoids simultaneous large-file hashing and temporary-cache writes. Bounded concurrency can be added later without changing the event contract.

### Isolate item failures

Each item runs inside its own error boundary. Duplicate, missing, unsupported, and source-unavailable failures become `item_failed` events. The runner does not stop unless the session manager itself becomes unusable.

Request-level failures, such as an empty item list or missing target folder, are rejected before a session starts and use normal JSON error responses.

### Refactor single-file registration into a reusable result

Extend the file-registration use case to return both:

- `file_id`
- `task_id`

The batch runner consumes this result for progress events. The old single-file HTTP route is removed with this change because the desktop app is its only intended consumer and the UI has not yet called the placeholder flow.

### Bridge task progress through a port

Define a library-side task snapshot port that returns current task status, progress, stage, and error for a set of task IDs. Bootstrap implements it with the existing task repository.

The import session monitor polls this port on a short interval and emits only changed snapshots. This avoids invasive changes to the scheduler while still providing near-real-time SSE updates. If polling latency becomes visible, the port can later be backed by an in-memory event broadcaster without changing the import contract.

### Use filesystem-backed directory browsing

Add a settings application use case and infrastructure adapter for active local and mounted-NAS locations.

- Local browsing covers readable local filesystem paths and starts at the operating system user home by default.
- Mounted-NAS browsing starts at its configured `root_path` or endpoint.
- Every request resolves within that root and rejects traversal and symlink escapes.
- Local entries return absolute source paths; NAS entries return root-relative source paths.
- The response includes name, kind, source path, size, and modified time.

Unsupported and deleted locations return distinct unavailable or unsupported errors.

### Use FastAPI SSE transport without the JSON envelope

The events route returns `text/event-stream` with:

- `Cache-Control: no-cache`
- `X-Accel-Buffering: no`
- Periodic `: ping` comments
- JSON `data` payloads
- SSE `id` values for reconnect

SSE responses are intentionally not wrapped in the normal JSON envelope.

### Add a dedicated frontend streaming transport

The import feature uses:

- The existing JSON API client to start a batch.
- A new stream client to consume SSE.

Browser development uses `EventSource` through the Vite proxy, which already injects the backend token. Packaged Tauri builds use a narrow Rust bridge that opens the backend SSE GET request with the token and forwards parsed chunks to the WebView; the token never enters page JavaScript.

### Model import dialog state locally

The import dialog keeps:

- Active storage tab
- Current directory per storage
- Directory query state
- A selection map keyed by storage ID and source path
- Import session and event state

Select all and invert selection operate on files in the current directory. Selection persists across navigation because it is keyed by source coordinates rather than row indices.

## Risks / Trade-offs

- [Large directories may return many entries] → Keep sorting deterministic and add UI virtualization if performance becomes visible.
- [Session event history can consume memory] → Bound retained events and expire completed sessions.
- [Backend restart loses the import stream] → Task records persist; show an interrupted import state and allow task-page recovery.
- [Polling task snapshots adds latency] → Start with a short interval and emit only changes; move to an event broadcaster only if needed.
- [SSE can be buffered by proxies] → Set no-cache headers and send heartbeat comments.
- [Tauri streaming bridge adds surface area] → Keep it narrowly scoped to import SSE and never expose the backend token to JavaScript.

## Migration Plan

1. Add storage directory browsing and tests.
2. Refactor file registration to expose file and task IDs.
3. Add the batch import session manager, task snapshot port, and SSE route.
4. Add desktop streaming transport and import dialog.
5. Remove the single-file import route and migrate its tests.
6. Verify browser development and packaged Tauri transports.

Rollback restores the single-file route and placeholder dialog; no database migration is required.
