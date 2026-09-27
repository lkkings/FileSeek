## Why

The user requested:
1. Remove `SearchBar` from `FolderDetailsView.tsx`.
2. The `SearchBar` in `LibraryPage.tsx` should always be present regardless of whether a folder is selected or not.
3. Once we enter a folder (i.e. `currentFolder` is active), searching should set/include the query's parameter `folder_id` to that folder's ID to restrict the results to only that folder.

## What Changes

- Remove any internal `SearchBar` and `localSearch` states from `FolderDetailsView.tsx`.
- Update `LibraryPage.tsx` to render the `SearchBar` at all times.
- Update `useFileSearch` hook or the submit call inside `LibraryPage.tsx` to pass/set the current folder's ID as the `folder_id` search parameter.

## Capabilities

### Modified Capabilities
- None (skip_specs is true).

## Impact

- `FolderDetailsView.tsx` will be modified.
- `LibraryPage.tsx` will be modified.
- `useFileSearch.ts` and `searchFiles` call will be updated to support passing a `folder_id` parameter.
