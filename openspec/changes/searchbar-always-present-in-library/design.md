## Context

See `proposal.md` for motivation. Currently, `LibraryPage.tsx` manages view modes sequentially using standard state flags. Search-to-folder-transition context is lost because entering search state currently resets the `currentFolder` context. In addition, sorting controls are duplicated across views with inconsistent styles, class names, and features (such as click-outside auto-closing).

## Goals / Non-Goals

**Goals:**
- Implement state-aware back-navigation mapping the transition: Folder Details -> Search Results -> Folder Details.
- Create a single, shared `SortControls` component used by both `SearchResultsView` and `FolderDetailsView`.
- Refactor folder detail card grid and style a side-by-side details sidebar in `FolderDetailsView`.
- Maintain absolute style and layout consistency with existing designs.

**Non-Goals:**
- Creating a separate routing library or path manager.
- Refactoring folder actions or file operations APIs.

## Decisions

### 1. Extracted SortControls Shared Component
We will create a new shared component `SortControls` in `desktop/src/components/SortControls.tsx`.
- **Properties:**
  - `options`: array of `{ value, label }` options.
  - `sortBy`: current selected option value.
  - `sortOrder`: `"asc" | "desc"`.
  - `onSortChange`: `(value: string, order: "asc" | "desc") => void`.
- **Behavior:**
  - Uses `useRef` and `useEffect` click-outside hook to automatically close the sort dropdown.
  - Keeps dropdown closed when selected, only toggles state cleanly.
- **Alternatives Considered:**
  - Re-writing separate inline click-outside hooks for both search results and folder details. *Rejected:* This continues code duplication and increases maintenance surface.

### 2. State-Driven View Transitions in LibraryPage
We will change the conditional layout rendering priority in `LibraryPage.tsx`:
- Render layout order:
  ```tsx
  {isSearching ? (
    <SearchResultsView ... />
  ) : currentFolder ? (
    <FolderDetailsView ... />
  ) : (
    <FolderSection ... />
  )}
  ```
- This allows `currentFolder` state to persist when `isSearching === true`. When a user clicks back from the search results view, `isSearching` is set to `false`, and the view naturally falls back to `<FolderDetailsView>` with the folder context preserved!

### 3. Inline Sidebar Layout inside FolderDetailsView
To show the detailed sidebar side-by-side inside `FolderDetailsView`, we will structure its content in a flex split layout:
- CSS class `.folder-details-split-container` wrapping the main list area and the `.result-sidebar` details aside.
- Clicking a card updates `selectedFile` state and toggles `sidebarOpen` to `true`.
- The backdrop and sidebar layout are styled identically to those in `SearchResultsView`.

## Risks / Trade-offs

- **[Risk] CSS Collision on Sidebar selectors** -> **[Mitigation]** Standardize CSS class naming (e.g. `.result-sidebar`) and place styles cleanly in `folder-details.css` to prevent layout overlaps.
