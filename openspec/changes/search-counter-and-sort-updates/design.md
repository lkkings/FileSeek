## Context

See `proposal.md` for motivation. Currently, the category counters on the folder details page are computed from the frontend array `viewFiles`, which is incorrect when the backend returns paginated results or filters are applied. In addition, the sorting states and `SortMode` are inconsistently typed or mapped, with some using custom labels such as `"default" | "time" | "size"`. We need to harmonize the types to exactly `"relevance" | "created_at" | "size"`, ensure the API requests enforce non-empty fields, and make use of the backend's `counter` field in `SearchResponseData` (and the corresponding `SearchResponse` on Python side).

## Goals / Non-Goals

**Goals:**
- Add/ensure `counter` is returned in `SearchResponseData` API envelope and mapped to the frontend response interface.
- Replace frontend category statistics counts in `FolderDetailsView` with counts loaded directly from the `counter` property of `SearchResponseData`.
- Restrict `SortMode` strictly to `"relevance" | "created_at" | "size"`.
- Default to `"relevance"` on the search results view and `"created_at"` on the folder details view.
- Update `SearchRequest` definition on backend/frontend to make `sort_by` and `sort_order` required.

**Non-Goals:**
- Redesigning the entire search page or folder pagination controls.
- Modifying vector search scoring/relevance computation logic.

## Decisions

### 1. Update the SearchRequest and SearchResponse Schemas
- **Decision**: Update backend schema `SearchRequest` (in `backend/src/fileseek/features/search/interfaces/http/schemas/__init__.py`) so that `sort_by` and `sort_order` are required fields (without omitting `Field` parameters that have default values, or keeping them with defaults but making sure they must be present in TypeScript interfaces and not omitted from client requests).
- **Rationals**: Eliminates any ambiguity about sort parameters being optional.
- **Alternatives**: Keeping them optional but setting defaults only on the backend. This is rejected as it doesn't solve the explicit typing sync requirement from the prompt.

### 2. Standardize SortMode across all modules
- **Decision**: Update `SortMode` in `desktop/src/components/SortControls.tsx` to:
  ```typescript
  export type SortMode = "relevance" | "created_at" | "size";
  ```
- **Rationale**: Replaces custom string mappings (`"default"`, `"time"`, etc.) with standard backend fields.

### 3. Replace local items-based count in FolderDetailsView
- **Decision**: Read `counter` directly from `searchResponse` (which is of type `SearchResponseData`) in `FolderDetailsView.tsx`.
- **Rationale**: The API response already computes the database category counts correctly under full scope, making it highly accurate even with paging or folder filters.

## Risks / Trade-offs

- **Risk**: Backend validation could fail if previous parts of the frontend call `/search` without providing `sort_by` and `sort_order`.
- **Mitigation**: Update all API request calls to always explicitly provide `sort_by` and `sort_order` in `useFileSearch.ts` and `useFolderFiles.ts`.
