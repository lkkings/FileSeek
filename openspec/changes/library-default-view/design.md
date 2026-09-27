## Context

Currently, `LibraryPage.tsx` directly renders `SearchResultsView` on load, completely bypassing the default library folder list representation. The components `FolderSection`, `FolderDialog`, and `DeleteFolderDialog` from `features/library` are available but unintegrated in the main page-level layout.

## Goals / Non-Goals

**Goals:**
- Dynamically toggle page layout between folder list (default library home) and search results list based on search execution state.
- Wire up full CRUD dialogs (`FolderDialog` and `DeleteFolderDialog`) for directory library folders within the `LibraryPage.tsx` layer.
- Integrate a highly responsive back button ("返回资源库") within the `SearchResultsView` to cleanly revert to the folder view and reset all search parameters.

**Non-Goals:**
- Modifying backend API route endpoints.
- Introducing a secondary global state manager (rely purely on React hook state variables).

## Decisions

### 1. View State Hook and Transitions
Introduce a boolean state `isSearching` inside `LibraryPage.tsx`.
- **Option A (Derive from query string)**: Show results if `filters.globalQuery` is not empty. (Rejected because if a user clears their search input while browsing results, the screen would unexpectedly switch back to the folder view).
- **Option B (Dedicated State Variable - Selected)**: Explicitly track `isSearching`. Set to `true` on successful `submitSearch()`, and set to `false` when clicking "返回资源库" (which simultaneously resets search filters and query state).

### 2. Back Button and UI Styling
Render the "Return to Library" (`返回资源库`) button inside `SearchResultsView.tsx` within the results heading, styling it to fit the existing cyberpunk-themed aesthetics.
- **Icon Representation**: Use the existing `chevron` icon inside the button, rotated 90 degrees clockwise (`transform: rotate(90deg)`) to serve as a high-fidelity left-pointing back icon.
- **Filter Cleanup**: Clicking the button calls an `onBack()` callback prop, resetting search inputs to ensure the search bar is cleared and ready for new workflows.

### 3. Folder Library Integration
Integrate `useFileLibrary` hook, `FolderSection`, and dialogs within `LibraryPage.tsx` using local states for current active modal (`"create" | "edit" | "delete" | null`) and the active target folder record.

## Risks / Trade-offs

- **[Risk]** Dialog submission issues causing state mismatch or errors.
  - **Mitigation**: Standardize handling of `runMutation` promise returned by `createFolder`, `updateFolder`, and `deleteFolder`, tracking submitting/loading and error messages in local page states.
