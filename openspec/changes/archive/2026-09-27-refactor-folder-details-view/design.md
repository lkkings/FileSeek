## Context

The `FolderDetailsView.tsx` and `folder-details.css` contain the UI and logic for the folder details screen in the Desktop client. They need styling adjustments and component structure refinement to support smaller category buttons, scrollable tags, and a unified sorting dropdown similar to the search results page.

## Goals / Non-Goals

**Goals:**
- Shrink the category buttons (`.category-tab-btn`) in size and padding to fit neatly.
- Remove advanced filter buttons and list/grid layout toggle buttons.
- Constrain tag pills in a single scrollable row (`white-space: nowrap`, `overflow-x: auto`).
- Add a text search input for local files.
- Replace the legacy 2-button sorting UI with a single sorting dropdown component/structure containing "时间" (date) and "大小" (size) sorting, with ascending/descending states integrated as per search results view.

**Non-Goals:**
- Do not add relevance/correlation sorting to the local file list.
- Do not refactor pagination or actual file cards except for filtering by search query.

## Decisions

- **Single Sorting Component**: We will refactor sorting to use state `sortBy` ("time" | "size") and `sortOrder` ("asc" | "desc") inside `FolderDetailsView`. Clicking on the currently active sort option in the dropdown will toggle its direction, while selecting a different sort option will switch to it with a default descending order.
- **Search Bar integration**: Add a search input inside `FolderDetailsView` directly above the files list (e.g. replacing the removed layout toggles or as a separate row below header).

## Risks / Trade-offs

- [Risk] Custom scrollbar on tags row might look unpolished. → Mitigation: Style the horizontal scrollbar with webkit-scrollbar properties to keep it minimal and clean, or hide scrollbar entirely while allowing touch/mouse drag scroll.
