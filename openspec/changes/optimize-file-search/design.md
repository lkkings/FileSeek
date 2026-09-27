## Context

The current user interface for the search results is implemented in `desktop/src/features/file-search/components/SearchResultsView.tsx` with styling located in `desktop/src/features/file-search/components/search-results.css`. Icons are rendered via `desktop/src/components/Icon.tsx`. This design aims to streamline sorting controls, remove visual clutter from lists, handle small screen real estate better, and make the details drawer navigation seamless.

## Goals / Non-Goals

**Goals:**
- Unify sorting and ordering into a single dropdown trigger/menu button.
- Remove redundant row actions from the list items.
- Support outside-click dismiss for the details panel/drawer on screen sizes <= 1024px.
- Hide inline previews in the main list rows on small screens <= 780px to save space.

**Non-Goals:**
- Modifying backend APIs or changing how search indices operate.
- Changing sorting logic beyond visual or interactive behaviors.

## Decisions

### 1. Unified Sort Dropdown Button
- **Rationale**: Currently, sorting mode selection and direction selection are split into two disjoint elements, making the header look cluttered. By moving the toggle order click handler to the currently active item inside the sort menu dropdown, we simplify the visual hierarchy.
- **Icon Addition**: Add `"sort-asc"` and `"sort-desc"` to `Icon.tsx`. The main sort button will dynamically render the icon matching the current sorting direction state (`sortOrder`).
- **Alternative**: Keep separate buttons but style them closer together. Rejected because it doesn't clean up the layout or align with modern unified sorting UX.

### 2. Backdrop Overlay for Drawer Dismissal
- **Rationale**: For screen widths <= 1024px, the details panel behaves as a fixed sidebar drawer. Adding a full-screen backdrop layer (`.sidebar-backdrop`) sibling to the sidebar allows capturing outside click events to trigger sidebar dismissal.
- **Visual Style**: A modern semi-transparent blur using `backdrop-filter: blur(4px); background: rgba(2, 8, 20, 0.6)` which blends elegantly with the existing glassmorphic theme.
- **Alternative**: Keep a visible close button and use document-wide event listeners. Rejected because a backdrop provides a stronger visual focus and natural dismiss target.

### 3. Grid Adjustments and Mobile Responsiveness
- **Rationale**: Removing `.result-actions` requires removing the 4th column from all grid layouts (`460px 346px minmax(0, 1fr) 74px` -> `460px 346px minmax(0, 1fr)`). Small screen responsive styling (`@media (max-width: 780px)`) will set `.result-preview` to `display: none;` to compress row heights on mobile views.

## Risks / Trade-offs

- **[Risk]**: Backdrop clicks might conflict with row selection clicks if z-index is set incorrectly.
  - **Mitigation**: Place `.sidebar-backdrop` below `.result-sidebar` but above the result list (`z-index: 999` vs `z-index: 1000` for drawer sidebar), ensuring that clicking the backdrop only dismisses the drawer while preventing clicks to underlying list rows while the drawer is open.
