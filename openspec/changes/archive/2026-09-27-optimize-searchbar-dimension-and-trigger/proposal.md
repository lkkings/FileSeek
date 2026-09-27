## Why

Based on design taste and specific feedback:
1. The search bar dimensions are too bulky and need to be more compact/slender.
2. In the folder details view, the search bar should not be visible initially. Instead, a search icon button should be clicked to toggle/display it.
3. The search bar must have a distinct, generous margin/gap from the containers directly below it to prevent layout crowding.

## What Changes

- Shrink the default `SearchBar` dimensions (lower the height from `64px` to `48px`, font size to `14px`, and icon size).
- Add state and button triggers in `LibraryPage.tsx` or `FolderDetailsView.tsx` so that when `currentFolder` is active, clicking a search icon reveals the `SearchBar` rather than rendering it open by default.
- Increase spacing/margin underneath the `SearchBar`/`AdvancedFilters` block in the main layout container.

## Capabilities

### Modified Capabilities
- None (skip_specs is true).

## Impact

- `search.css` will be modified to shrink `SearchBar` dimensions and adjust margins.
- `LibraryPage.tsx` will be modified to support toggleable folder-search behavior and correct spacing.
