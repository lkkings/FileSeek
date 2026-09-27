## Why

The user requested that the search bar in the folder details view should use the original `SearchBar` component (`desktop/src/features/file-search/components/SearchBar.tsx`) rather than a custom local search input.

## What Changes

- Import and use the original `SearchBar` component inside `FolderDetailsView.tsx`.
- Pass matching props: `query`, `onQueryChange`, `onClear`, `onOpenAdvanced`, `advancedOpen`, `onSubmit`.
- Style it appropriately so that the SearchBar renders perfectly within the sidebar-compatible Folder Details layout (optionally hiding the advanced filters toggle if they are out of scope or disabling advanced filters actions inside folder details).

## Capabilities

### Modified Capabilities
- None (skip_specs is true).

## Impact

- `FolderDetailsView.tsx` will be modified.
