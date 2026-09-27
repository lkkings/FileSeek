## Why

The current library search results page contains a redundant file category tab selector that conflicts with advanced filter settings. Additionally, the list sorting is limited to descending order and name sorting (which is less relevant than date, size, and relevance). Finally, the layout gets cramped when displaying file details, which hinders visibility under different screen resolutions.

## What Changes

- **Category Selector Removal**: Remove the top category tab selector on the search results page to eliminate redundant UI.
- **Improved Sorting Options**: Restructure the sorting dropdown to support only "Relevance" (default), "File Size", and "Date" sorting.
- **Sorting Order Support**: Add a direction button next to the sorting dropdown supporting both Ascending (正序) and Descending (逆序) ordering across all sorting modes.
- **Sidebar Details Panel**: Implement an expandable/collapsible details sidebar that opens on item selection, displaying comprehensive metadata, tags, and larger image/video preview components.
- **Responsive Adaptive Layout**: Update the grid-based list and sidebar layout to be highly fluid. Under full-screen resolutions, the list dynamically scales without cramping items. On small screens (<= 1024px), the details sidebar transitions into a smooth slide-in drawer.

## Capabilities

### New Capabilities
- `file-search/results`: Specification for search results layout, adaptive behaviors, sorting controls, and sidebar detailed view.

### Modified Capabilities

None.

## Impact

- `desktop/src/features/file-search/components/SearchResultsView.tsx`
- `desktop/src/features/file-search/components/search-results.css`
