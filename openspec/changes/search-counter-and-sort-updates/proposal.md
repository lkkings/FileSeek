## Why

The current file statistics and categories counter on the frontend relies on the returned items list, which is incorrect under paging or filtering. Additionally, sort options on requests are optional and inconsistency exists between folder details and search results default sorting modes.

## What Changes

- **Added `counter` in search response**: SearchResponseData contains a `counter` field specifying total counts per file category (`{"image": 0, "document": 0, "video": 0}`).
- **Frontend Category Counter Refactoring**: Replace the frontend-calculated category/items counts with the backend-returned `counter` field values.
- **Mandatory sort parameters**: `SearchRequest`'s `sort_by` and `sort_order` cannot be empty (they are required fields).
- **Refactored Sort Controls**: Restrict `SortMode` in `SortControls` strictly to `"relevance" | "created_at" | "size"`.
- **Default sorting modes**:
  - Search results page (`SearchResultsView`) defaults to `"relevance"`.
  - Folder details page (`FolderDetailsView`) defaults to `"created_at"`.

## Capabilities

### Modified Capabilities
- `file-search/results`: Modifies the sorting modes to support `"relevance" | "created_at" | "size"` and changes how file list counters are tracked/rendered using the backend `counter`.

## Impact

- `backend/src/fileseek/features/search/interfaces/http/schemas/__init__.py`: Update `SearchRequest` to require `sort_by` and `sort_order` with defaults, ensuring they are always validated. Update `SearchResponse` to serialize the `counter` properly.
- `desktop/src/services/api/search.ts`: Update `SearchRequest` typescript interface and `SearchResponseData` typescript interface.
- `desktop/src/components/SortControls.tsx`: Update `SortMode` to `"relevance" | "created_at" | "size"`.
- `desktop/src/features/file-search/components/SearchResultsView.tsx`: Replace state and use `"relevance"` as default.
- `desktop/src/features/library/components/FolderDetailsView.tsx`: Replace category statistics counts with the response `counter` and default sorting to `"created_at"`.
