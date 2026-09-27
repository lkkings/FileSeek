## Context

Currently, `LibraryPage.tsx` conditionally hides the `SearchBar` when `currentFolder` is set:
```tsx
          {!currentFolder && (
            <>
              <SearchBar ... />
              ...
            </>
          )}
```
We need to render the `SearchBar` unconditionally at the top of the main area.
Additionally, when a search is triggered, we need to pass `folder_id` if we are currently inside a folder.

## Goals / Non-Goals

**Goals:**
- Remove the local SearchBar and search states from `FolderDetailsView.tsx`.
- Unconditionally render `SearchBar` in `LibraryPage.tsx` at the top of the screen.
- Pass `folder_id` to search API / hook when `currentFolder` is selected, so search executes restricted to that folder.

**Non-Goals:**
- Do not affect global search behavior when outside of any folder.
