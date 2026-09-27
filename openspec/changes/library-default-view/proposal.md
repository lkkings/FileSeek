## Why

The current library page directly shows search results on load, which is confusing as users expect to see their folders and file list (the library home view) by default. The search results screen should only appear after a search has been completed, with an intuitive "Return to Library" navigation flow to switch back to the home view.

## What Changes

- **Default Home View**: The library page now defaults to the folder layout (`FolderSection`) upon entry, showing the folder list and supporting folder CRUD dialogs.
- **Search Results View**: The search results screen (`SearchResultsView`) is hidden initially and only displayed after the user submits a search.
- **Back to Library Navigation**: A "Return to Library" (`返回资源库`) button is added to the search results layout, resetting search query/filters and restoring the default folder library view.

## Capabilities

### New Capabilities
<!-- None -->

### Modified Capabilities
- `file-search/results`: Modifies the page-level workflow of the file library to show folder grids by default and only display search results when a search is completed, with a back navigation button.

## Impact

- `desktop/src/pages/library/LibraryPage.tsx`
- `desktop/src/features/file-search/components/SearchResultsView.tsx`
- `desktop/src/features/file-search/components/search-results.css`
