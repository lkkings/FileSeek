## Context

The original `SearchBar` component resides in `desktop/src/features/file-search/components/SearchBar.tsx`.

## Goals / Non-Goals

**Goals:**
- Use the original `SearchBar` in `FolderDetailsView.tsx`.
- Keep the `SearchBar` layout elegant and visually integrated.

**Non-Goals:**
- Do not trigger global search; instead, the `SearchBar` inside `FolderDetailsView` should filter files locally within the folder using its `query` prop and `onQueryChange`.
