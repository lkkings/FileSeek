## 1. UI Styles Refactoring

- [x] 1.1 Decrease the padding and font size of `.category-tab-btn` elements to make them smaller and more robust when the sidebar expands. Verify in browser/desktop preview.
- [x] 1.2 Refactor the tag list container `.tag-pills-list` to support a single-line horizontal scrollable view instead of wrapping. Style the scrollbar to be hidden or very minimal. Verify tags overflow correctly and scroll.

## 2. Component Layout and Logic Refinement

- [x] 2.1 Remove the advanced filter button and layout grid/list toggle buttons from `FolderDetailsView.tsx`. Verify buttons are gone from header.
- [x] 2.2 Add a local search bar component/element to `FolderDetailsView.tsx` with clear/reset support, and filter files dynamically using this search input. Verify file lists are filtered correctly on typing.
- [x] 2.3 Refactor the sorting selector component inside `FolderDetailsView.tsx` to match the style/dropdown behaviour of the SearchResultsView (combined sort field & order dropdown, with only "修改时间" and "文件大小" options). Verify sorting behavior operates correctly.
