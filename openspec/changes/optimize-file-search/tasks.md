## 1. Icon Assets Update

- [x] 1.1 Add `"sort-asc"` and `"sort-desc"` to the `IconName` type and `iconPaths` registry in `desktop/src/components/Icon.tsx`, and verify the SVG paths render correct upward and downward arrows.

## 2. Core Search View Component Refactoring

- [x] 2.1 Refactor sort controls in `desktop/src/features/file-search/components/SearchResultsView.tsx`: remove the standalone sort-order button, use the dynamic `sortOrder === "asc" ? "sort-asc" : "sort-desc"` icon inside `sort-button`, and implement direction toggle on clicking the active option in `sort-menu`. Verify sorting direction changes correctly on click.
- [x] 2.2 Remove list-level action buttons and preview eye icon (`.result-actions` section) from `SearchResultsView.tsx`, and clean up any unused `actionMenuId` states and click handlers. Verify the results list items still support selection row clicks and details expand cleanly.
- [x] 2.3 Add backdrop component `<div className="sidebar-backdrop" onClick={() => setSidebarOpen(false)} />` and remove the close button from the `.sidebar-header` inside the details panel sidebar in `SearchResultsView.tsx`. Verify details drawer can close by clicking the backdrop on drawer screens.

## 3. Responsive Styling Adjustments

- [x] 3.1 Adjust CSS grid and styling rules in `desktop/src/features/file-search/components/search-results.css`: remove the fourth grid column from all layouts (`.result-row`, `.sidebar-expanded .result-row`, and mid-range media query), remove classes for `.result-actions`, `.sort-order-button`, and configure `.sidebar-backdrop` layout, position, and transition. Verify columns stretch gracefully across different widths.
- [x] 3.2 Add styles in `search-results.css` under the `@media (max-width: 780px)` query to set `.result-preview { display: none; }`. Verify inline item previews are completely hidden on mobile sizes while remaining accessible in the drawer.
