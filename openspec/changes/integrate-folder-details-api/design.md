## Context

Currently, `FolderDetailsView.tsx` uses static mock files (`INITIAL_FILES`). To support dynamic file display matching actual indexed data, we need to implement real API communication using the backend's `/api/v1/search` endpoint.
No modifications can be made to the backend, meaning all querying, pagination, search parameters, and action responses must conform strictly to the backend schemas defined in `dosc/openapi.json`.

## Goals / Non-Goals

**Goals:**
- Implement dynamic loading of files in `FolderDetailsView` via `/api/v1/search`.
- Maintain exact visual rendering and styling of file entries while using live database entries.
- Wire folder-specific categories (All, Documents, Images, Videos) and tag filters into the search query.
- Wire Move To Folder, Delete (Move to Recycle), and Restore actions to reload and synchronize views.

**Non-Goals:**
- Modifying any backend code or database schemas.
- Adding full-text search capability outside of the FolderDetailsView's scope (which is already handled by the global search feature).

## Decisions

### Decision 1: Create a unified React Hook for Folder Files Fetching
- **Approach**: Create `useFolderFiles.ts` under `desktop/src/features/library/hooks/` using TanStack Query (`useQuery`).
- **Rationale**: Keeps asynchronous state management, cache invalidation, and request formulation separate from the UI components, adhering to the Feature-based Architecture in `AGENTS.md`.
- **Alternatives Considered**: Direct fetch or local state management inside the view component (rejected due to violation of separating business logic from UI in `AGENTS.md`).

### Decision 2: Query formulation with empty natural-language query
- **Approach**: Pass `query: ""` to the `/api/v1/search` POST endpoint, combined with `folder_id: current_folder_id`.
- **Rationale**: The backend schema requires the `query` field. By providing an empty string `""`, we query all files inside the specified `folder_id` without filtering by keyword relevance, but keeping sorting and other parameters fully functional.

### Decision 3: Parameter/Data structures normalization
- **Approach**: Map the fields of the returned `FileItem` from `/api/v1/search` to the React state expected by the view.
- **Rationale**: The backend `FileItem` structure uses properties like `file_id` and `file_name`, which will be mapped cleanly to the component properties without modifying the underlying UI layout.

## Risks / Trade-offs

- **[Risk]** Backend `/api/v1/search` performance when returning a large number of files.
  - *Mitigation*: Leverage backend pagination (`page_number` and `page_size`) in the hook to prevent loading huge payloads unnecessarily.
