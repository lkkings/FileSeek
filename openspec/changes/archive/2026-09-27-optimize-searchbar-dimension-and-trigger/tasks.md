## 1. Implement Smaller SearchBar and Spacing

- [ ] 1.1 Shrink `.top-search-wrap` height to `48px`, adjust border-radius, font-size, and icon sizes in `search.css`.
- [ ] 1.2 Add a distinct margin/gap bottom (e.g. `margin-bottom: 24px` on `.top-search-wrap`) to keep a clean, premium visual distance.

## 2. Interactive Search Icon Toggle in Folder View

- [ ] 2.1 Update `LibraryPage.tsx` with a state `showFolderSearch`. If `currentFolder` is set, render the SearchBar only if `showFolderSearch` is true. Provide a Search icon toggle button at the top/breadcrumb header of `FolderDetailsView` or within `LibraryPage` so clicking it toggles the SearchBar open.
- [ ] 2.2 Verify everything works perfectly and type checks successfully.
