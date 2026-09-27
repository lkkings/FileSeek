## Why

The search results list page (`SearchResultsView.tsx`) and the folder details page (`FolderDetailsView.tsx`) have highly duplicated rendering markup, local UI helper states, pagination, and file detail drawer elements. This makes the frontend codebase harder to maintain and scale. In addition, the types and fields used inside these views are mapped to custom frontend definitions rather than fully aligning with the backend-returned `FileItem` data schema.

## What Changes

This is a pure refactor that introduces no new behavior. The changes are:
- **Unify with Backend Schema**: Eliminate separate frontend mappings (`SearchResultItem` / custom `FileItem`) and fully adopt the backend-returned `FileItem` data structures across both views.
- **Extract Shared Components**:
  - **`FileDetailDrawer.tsx`**: Extract the backdrop and side panel rendering for showing file meta details into a shared component.
  - **`Pagination.tsx`**: Extract pagination controls (prev, next, and active state) into a reusable shared component.
  - **`FileRowItem.tsx`**: Extract search results row item rendering including batch checkbox overlay and long-press event handlers.
  - **`FileGridItem.tsx`**: Extract folder file grid item card rendering including batch checkbox overlay and long-press event handlers.
- **Deduplicate Code**: Drastically reduce lines of code in `SearchResultsView.tsx` and `FolderDetailsView.tsx` by delegating list, drawer, and pagination rendering to the extracted shared components.

## Capabilities

### New Capabilities
<!-- Skip spec generation as this is a pure refactor change -->

### Modified Capabilities
<!-- Skip spec generation as this is a pure refactor change -->

## Impact

- `desktop/src/components/FileDetailDrawer.tsx` (New)
- `desktop/src/components/Pagination.tsx` (New)
- `desktop/src/features/file-search/components/FileRowItem.tsx` (New)
- `desktop/src/features/library/components/FileGridItem.tsx` (New)
- `desktop/src/features/file-search/components/SearchResultsView.tsx`
- `desktop/src/features/library/components/FolderDetailsView.tsx`
