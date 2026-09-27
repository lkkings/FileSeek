## 1. Backend Schema Changes

- [x] 1.1 Update `SearchRequest` schema in `backend/src/fileseek/features/search/interfaces/http/schemas/__init__.py` to ensure `sort_by` and `sort_order` are required fields (no default or have defaults, but explicitly required in schema / cannot be null) and verify with backend tests.
- [x] 1.2 Update `SearchResponse` schema in `backend/src/fileseek/features/search/interfaces/http/schemas/__init__.py` to properly serialize and provide the `counter` field in the response.

## 2. Frontend Interface and Hook Changes

- [x] 2.1 Update `SearchRequest` and `SearchResponseData` in `desktop/src/services/api/search.ts` to include `counter` as `Record<string, number>` and make `sort_by` and `sort_order` mandatory fields.
- [x] 2.2 Refactor `useFileSearch` hook in `desktop/src/features/file-search/hooks/useFileSearch.ts` to include explicit required parameters for `sort_by` and `sort_order` in the API request, and default the search view sorting state properly to `"relevance"`.
- [x] 2.3 Refactor `useFolderFiles` hook in `desktop/src/features/library/hooks/useFolderFiles.ts` to include explicit required parameters for `sort_by` and `sort_order` (default to `"created_at"`).

## 3. Frontend View and Component Modifications

- [x] 3.1 Update `SortControlsProps` and `SortMode` in `desktop/src/components/SortControls.tsx` to restrict `SortMode` strictly to `"relevance" | "created_at" | "size"`.
- [x] 3.2 Update `SearchResultsView.tsx` to use the updated `SortMode`, defaulting sorting to `"relevance"` and verifying it sorts correctly and sends the correct parameters.
- [x] 3.3 Update `FolderDetailsView.tsx` to use the updated `SortMode`, defaulting sorting to `"created_at"`, and replace local items-based counting logic with the `counter` field from the API response (`searchResponse.data.counter` or `searchResponse.counter`).
