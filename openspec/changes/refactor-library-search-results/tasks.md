## 1. Remove Redundant Tabs & Refactor Sorting UI

- [x] 1.1 Remove category selection tab selectors from `SearchResultsView.tsx` and verify that the tab bar element `.result-tabs` is completely deleted from the rendered DOM.
- [x] 1.2 Restructure sorting dropdown options to only include "Relevance" (default), "File Size", and "Date" sorting; verify by opening the dropdown and confirming only these three modes are present.
- [x] 1.3 Add a sorting direction button adjacent to the dropdown; verify clicking it toggles ascending/descending states and changes sorting order accordingly.

## 2. Implement Splitted Details Sidebar & Layout Logic

- [x] 2.1 Add `sidebarOpen` state and grid/flex layout containers inside `SearchResultsView.tsx`; verify the sidebar opens successfully upon clicking a list item row.
- [x] 2.2 Populate the sidebar with selected file metadata (full name, path, date, size), tags, description, and preview components; verify that correct content updates when choosing different items.
- [x] 2.3 Implement the close/collapse button inside the sidebar header; verify that clicking it closes the sidebar.

## 3. Responsive Styling and Fluid Self-Correction

- [x] 3.1 Create fluid layout classes in `search-results.css` ensuring columns in `.result-row` gracefully adapt without wrapping/overlap when the sidebar is open; verify layout on medium screen resolutions.
- [x] 3.2 Add CSS media queries to turn the sidebar details container into a full-height right slide-in drawer on screens with widths <= 1024px; verify smooth visual transitions on narrow screen resolutions.
