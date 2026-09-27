## Context

The desktop app follows `desktop/AGENTS.md`: React 19, TypeScript, Lingui, TanStack Query, feature-based architecture, and strict UI → feature hook → API service → API client dependency direction. Pages and UI components must not call API services directly.

The backend wraps successful responses in `{ status, data, error }`. The OpenAPI file describes the endpoints, while the backend Pydantic response schemas provide the exact field names used by the frontend:

| Area | Exact response shape |
| --- | --- |
| Recent list | `items`, `page_number`, `page_size`, `total`, `has_more`; each item has `id`, `file_id`, `accessed_at`, and optional `file` |
| Recycle list | `items`, `page_number`, `page_size`, `total`, `has_more`; each item has `id`, `original_file_id`, `original_name`, `original_path`, `deleted_at`, `file_type`, `size` |
| Tasks list | `tasks`, `counts`, `page`, `page_size`, `total`; each task has `id`, `file`, `status`, `progress`, `stage`, `error_message`, `created_at` |

## Goals / Non-Goals

**Goals:**

- Use backend-identical TypeScript request and response types.
- Make all three pages genuinely interactive with pagination, selection, mutation, feedback, and cache refresh.
- Preserve the existing dark visual system and responsive behavior.
- Keep API access behind feature hooks and services.

**Non-Goals:**

- No backend API changes.
- No new third-party dependency.
- No WebSocket or SSE transport.
- No global state store for page-local selection state.
- No invented per-stage completion history; the task API exposes only the current stage and overall progress.

## Decisions

### API contracts and DELETE body support

Define response interfaces exactly as the backend serializes them. `RecycleItem.size` is a string and Recent's nested file uses `id`, `name`, and `folder_id`, so adapters are required only at the feature-hook boundary to create UI row models.

Add an optional body parameter to `ApiClient.delete`. This keeps body serialization, prefixing, transport, and envelope parsing inside the shared client and removes the current `(client as any).send` workaround.

### Recent access

`useRecentAccess` owns the page state and query. It maps each valid `item.file` into the existing `FileItem` UI model while retaining `item.id` as the deletion ID. Selection tracks record IDs, not file IDs.

Opening a file from `FileDetailDrawer` invokes a callback supplied by the page. `RecentPage` uses a feature mutation to send one `POST /api/v1/recent` request with `{ file_id }`, then invalidates the recent list. `FileDetailDrawer` no longer imports or calls the recent API service.

Because the backend has only `DELETE /api/v1/recent/{record_id}`, batch deletion sends one request per selected record with `Promise.allSettled`. It reports partial success and refreshes successful deletions; it does not pretend the operation is atomic.

### Recycle Bin

`useRecycleBin` provides the list query and mutations:

- `POST /api/v1/recycle` with `{ file_ids }` moves search or folder files to the Recycle Bin.
- `DELETE /api/v1/recycle` with `{ item_ids }` permanently removes selected records.
- `POST /api/v1/recycle/restore` with `{ item_ids }` restores selected records.

`RecycleRowItem` is a typed recycle-specific component. It reuses `result-row`, `search-row-checkbox`, `file-type-icon`, and existing action button classes while displaying `original_name`, `original_path`, `deleted_at`, and `size`. It never casts `RecycleItem` to `FileItem`.

Search results and folder details do not import the recycle feature. Their pages pass a shared recycle mutation callback into them, preserving feature boundaries and allowing both contexts to invalidate their own list queries after a successful move.

### Tasks

`useTasks` uses the exact task response shape and polls every 2 seconds while the page is visible. TanStack Query continues to own server state and cache invalidation. The status filter is a typed union of `queued`, `processing`, `completed`, and `failed`; no `pending` value is sent.

`TaskRowItem` reuses the result-row visual language and displays:

- file name and path from `task.file`
- status badge with existing palette-compatible colors
- overall progress bar using `task.progress`
- the four stage labels: `extracted` 提取, `encoded` 编码, `classify` 分类, `indexed` 构建索引
- `error_message` for failed tasks
- retry action for failed tasks

For `processing`, only the API-provided current stage is highlighted. For `completed`, all stages are shown as complete. For `queued` and `failed`, the UI does not fabricate completion history.

### Visual and responsive behavior

The pages continue using `search-results-screen`, `results-heading`, `result-list`, `result-list-container`, `results-content-split`, `Pagination`, `Notice`, `DeleteConfirmDialog`, and the batch operation bar.

New row styling stays within the existing dark palette, 15px row radius, 7px list gap, 14–16px text sizes, and established hover/selected treatments. Existing breakpoints remain authoritative: narrow rows between 781px and 1180px, single-column rows at 780px and below, and a fixed right drawer at 1024px and below.

### i18n and architecture

Every new user-visible string uses `useTranslate`. Feature-specific rows and hooks remain in their feature directories. Cross-feature composition occurs in pages. API services remain in `services/api/`, and no page or component calls `fetch` or an API service directly.

## Risks / Trade-offs

- [Recent batch deletion is not atomic because the backend only supports single-record deletion] → Use `Promise.allSettled`, report partial success, and expose backend errors without clearing failed selections.
- [Polling is less efficient than a push transport] → The current API has no realtime endpoint; 2-second TanStack Query polling gives near-real-time updates without adding a dependency.
- [Task stage history is unavailable] → Render only the current stage and overall progress; do not infer or fabricate completed-stage state.
- [Search and folder pages need recycle behavior] → Pass callbacks from pages so feature modules remain decoupled and each page can invalidate the appropriate query.
- [Visual changes could drift from the existing design] → Reuse existing classes and breakpoints; add only narrowly scoped task and recycle styles.

## Migration Plan

1. Correct API types and shared DELETE body handling.
2. Add typed feature hooks and row components.
3. Wire pages, search results, folder details, and preview opening.
4. Add focused tests for service request shape and feature behavior.
5. Run typecheck, lint, tests, and the Vite development server; inspect desktop and responsive layouts.

Rollback is limited to the frontend files in this change because no backend, schema, dependency, or persistence migration is introduced.
