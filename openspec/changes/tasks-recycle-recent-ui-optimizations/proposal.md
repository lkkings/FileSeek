## Why

The Recent, Recycle Bin, and Tasks pages currently diverge from the backend API contracts and from the desktop application's established visual system:

1. Recent access records use the wrong response shape and try to call a nonexistent batch-delete endpoint.
2. Recycle Bin rows are forced into `FileItem` with `any`, and moving files to the Recycle Bin uses the wrong path in folder details and is only simulated in search results.
3. Tasks use an outdated `items/task_id/task_type/file_name` response shape, include an invalid `pending` status, and do not refresh in near real time.
4. The pages contain architecture violations: pages and UI components call API services directly instead of going through feature hooks.

## What Changes

- Align `services/api/recent.ts`, `services/api/recycle.ts`, and `services/api/tasks.ts` with the backend request and response schemas.
- Extend the shared API client so `DELETE` requests can carry an optional JSON body without accessing its private `send` method.
- Implement paginated Recent access listing, record deletion by backend record ID, and one access-record request when a file is opened from preview details.
- Implement Recycle Bin listing, permanent deletion, restoration, and moving selected files to the Recycle Bin from search results and folder details.
- Implement task listing and retry using the exact backend task shape, status filters, counts, progress, and current stage; poll active task data with TanStack Query.
- Add typed feature components for Recycle Bin and task rows while reusing the existing result-row, pagination, batch bar, dialog, notice, icon, and button styles.
- Keep all user-visible text in Lingui translations and preserve the existing dark theme, spacing, typography, and responsive breakpoints.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. This change is scoped to existing desktop frontend behavior and already-available backend API capabilities. Specs are intentionally skipped with `skip_specs: true`.

## Impact

- `desktop/src/services/api/client.ts`
- `desktop/src/services/api/recent.ts`
- `desktop/src/services/api/recycle.ts`
- `desktop/src/services/api/tasks.ts`
- `desktop/src/features/recent/`
- `desktop/src/features/recycle/`
- `desktop/src/features/tasks/`
- `desktop/src/features/file-search/components/SearchResultsView.tsx`
- `desktop/src/features/library/components/FolderDetailsView.tsx`
- `desktop/src/components/FileDetailDrawer.tsx`
- `desktop/src/pages/recent/RecentPage.tsx`
- `desktop/src/pages/recycle/RecyclePage.tsx`
- `desktop/src/pages/tasks/TasksPage.tsx`
- Existing search-result, feature, and page CSS where task and recycle row styling is added
