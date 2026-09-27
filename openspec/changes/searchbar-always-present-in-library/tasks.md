## 1. Extract and Unify SortControls Component

- [x] 1.1 Create the reusable `SortControls.tsx` component in `desktop/src/components/SortControls.tsx` and verify it renders cleanly with customized sorting options.
- [x] 1.2 Refactor `SearchResultsView.tsx` to use the unified `SortControls` component and verify it displays Relevance, Size, and Date options with functional sorting.
- [x] 1.3 Refactor `FolderDetailsView.tsx` to use the unified `SortControls` component and verify it displays Size and Date options (no Relevance).

## 2. Refactor LibraryPage Layout & Navigation Logic

- [x] 2.1 Refactor conditional view rendering in `LibraryPage.tsx` so that `isSearching` check precedes `currentFolder` check.
- [x] 2.2 Verify that clicking "返回" from search results correctly restores either root folders view or folder details view depending on whether `currentFolder` is set.
- [x] 2.3 Verify that the search parameter `folder_id` is supplied as the active folder ID when searching inside a folder, and null/empty when searching from the root folders list.
- [x] 2.4 Update SearchResultsView back button text from "返回资源库" to "返回".

## 3. Implement Toggleable Search Bar & Inline Details Sidebar in FolderDetailsView

- [x] 3.1 Verify toggle behavior of SearchBar inside folder details is reactive to clicking the header search icon.
- [x] 3.2 Refactor folder details main layout into a split layout to accommodate a side-by-side details sidebar.
- [x] 3.3 Add `selectedFile` and `sidebarOpen` states to `FolderDetailsView.tsx` and verify that clicking a file card expands the split details sidebar.
- [x] 3.4 Wire up preview thumbnail and metadata displays inside `FolderDetailsView`'s details sidebar to match the layout of the search results sidebar.
