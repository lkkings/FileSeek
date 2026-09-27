## Why

Users need more refined navigation, flexible folder search controls, unified sorting controls, and inline file details viewing when browsing the resource library, specifically inside folders and within search result lists.

## What Changes

- **Navigation Flow Improvement**: Changed the back button text from "返回资源库" to "返回", and adjusted the routing so that if a search was triggered from within a folder, back-navigation correctly restores that folder's Details View rather than resetting to the root list.
- **Toggleable Folder Search**: Allows users to dynamically toggle the search bar on/off inside a folder view to conserve screen space.
- **Inline Details Sidebar**: Clicking a file card within the folder details view now expands a responsive side-by-side details sidebar identical to the search results page.
- **Unified Sorting Component**: Extracted duplicate sorting code from `SearchResultsView` and `FolderDetailsView` into a single reusable, click-outside-aware `SortControls` component, which fixes a bug in `FolderDetailsView` and adds click-outside auto-closing to both views.

## Capabilities

### Modified Capabilities
- `file-search/results`: Enhance search results and folder details page behaviors, including search toggles, inline details, and unified sorting option configuration.

## Impact

- `desktop/src/pages/library/LibraryPage.tsx`
- `desktop/src/features/library/components/FolderDetailsView.tsx`
- `desktop/src/features/file-search/components/SearchResultsView.tsx`
- `desktop/src/components/SortControls.tsx` (new component)
