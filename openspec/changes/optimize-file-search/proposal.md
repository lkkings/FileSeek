## Why

The current search results layout has several user experience issues: sorting is split into two disjoint buttons (mode and order), list-level action and preview buttons are redundant since a full right details sidebar exists, small screen list items display cramped previews, and the details drawer requires a manual close button click rather than allowing standard backdrop-dismiss.

## What Changes

- **Unified Sorting Interaction**: Remove the separate sorting order button. Allow clicking the active sorting mode option in the dropdown to toggle between ascending and descending order. Use separate, specific icons for ascending vs. descending.
- **Redundancy Removal in Lists**: Remove inline preview and action buttons from list rows, as these capabilities are fully covered by the right details panel.
- **Responsive Preview Adaptation**: On small screens (<= 780px), completely hide list-level file previews to optimize tight horizontal space while retaining the preview in the right drawer/sidebar.
- **Sleek Drawer Backdrop Dismiss**: Support clicking outside the details drawer to close it on small screen sizes (<= 1024px) by rendering a modern, blurred backdrop. Remove the manual close button from the sidebar header.

## Capabilities

### Modified Capabilities
- `file-search/results`: Update the sorting interactions, list row layout, responsive preview visibility, and sidebar drawer behavior.

## Impact

- `desktop/src/components/Icon.tsx`
- `desktop/src/features/file-search/components/SearchResultsView.tsx`
- `desktop/src/features/file-search/components/search-results.css`
