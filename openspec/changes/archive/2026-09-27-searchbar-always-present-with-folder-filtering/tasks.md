## 1. Implement Changes

- [ ] 1.1 Update `useFileSearch.ts` to accept an optional `folder_id` parameter inside `submitSearch` or maintain it as part of its internal state/filters. Let's make `submitSearch` accept an optional `folderId: string | null` or include `folderId` in its parameters.
- [ ] 1.2 Modify `LibraryPage.tsx` to keep the `SearchBar` unconditionally visible. Pass the `currentFolder?.id` to `submitSearch` when triggering a search.
- [ ] 1.3 Remove `SearchBar` import, rendering markup, and styling override from `FolderDetailsView.tsx`.
- [ ] 1.4 Verify type safety and compile success.
