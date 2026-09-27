## 1. Search Results Component Updates

- [x] 1.1 Add `onBack` optional callback prop to `SearchResultsView` component in `desktop/src/features/file-search/components/SearchResultsView.tsx` and verify compiling.
- [x] 1.2 Implement the "Return to Library" (`返回资源库`) button next to the search query text in the results-heading element under a `.results-title-group` and verify it triggers `onBack` callback when clicked.
- [x] 1.3 Add CSS styles for `.results-title-group`, `.back-button`, and rotated `.back-button svg` in `desktop/src/features/file-search/components/search-results.css` and verify correct layout rendering.

## 2. Main Page Layout and Logic Integration

- [x] 2.1 Import `FolderSection`, `useFileLibrary`, dialogs, and types into `desktop/src/pages/library/LibraryPage.tsx` and verify imports are clean.
- [x] 2.2 Add `isSearching` state and folder CRUD handling states (activeDialog, selectedFolder, dialogSubmitting, dialogError) to `LibraryPage` and verify state logic.
- [x] 2.3 Update `handleSearch` to set `isSearching` to `true` upon search execution, and implement `handleReturnToLibrary` to clear searching state and reset filters.
- [x] 2.4 Conditionally render `SearchResultsView` or `FolderSection` and its CRUD dialogs (`FolderDialog`, `DeleteFolderDialog`) in the JSX of `LibraryPage.tsx` and verify the entire page compiles and displays folders by default.
