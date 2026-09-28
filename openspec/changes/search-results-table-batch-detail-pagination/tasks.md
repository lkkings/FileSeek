## 1. Shared File Row

- [x] 1.1 Extract or generalize the folder details file row so it can render preview, file name, time, size, and tags while preserving existing long-press, click, double-click, and selection callbacks; verify the existing `FolderDetailsView` tests still pass.
- [x] 1.2 Apply the single-column search-results row layout using the shared row and folder table visual tokens; verify `SearchResultsView` renders every required field without a multi-column result grid.

## 2. Search Pagination

- [x] 2.1 Extend `useFileSearch` to maintain page number, page size, and sorting request state, and allow searches to request an arbitrary page with unchanged filters; verify the hook requests the selected page, size, and sorting parameters.
- [x] 2.2 Wire the shared `Pagination` component into `SearchResultsView` and `LibraryPage`, clear selection on page change, and recalculate the nearest valid page after a refresh removes the current page; verify page changes request and display the correct result set.
- [x] 2.3 Remove the search-results category tab bar and its page-local category counting; verify advanced file-type filtering still works and no “全部 / 文档 / 图片 / 视频” tab bar is rendered.

## 3. File Management Interactions

- [x] 3.1 Implement non-batch row clicks to open `FileDetailDrawer` and batch-mode row clicks to toggle selection; verify drawer open, close, and batch-selection behavior in component tests.
- [x] 3.2 Implement long-press batch mode with select all, invert selection, cancel, and confirmed batch move-to-recycle; verify confirmation is required, selection clears on success, results refresh, and selection remains on failure.
- [x] 3.3 Implement confirmed batch move-to-folder using `MoveFilesDialog`, the existing folder list, and `useMoveFilesToFolder`; verify destination selection is required, success refreshes the current page, and failure preserves selection and the dialog state.

## 4. Verification

- [x] 4.1 Update `SearchResultsView`, `useFileSearch`, `FileDetailDrawer`, shared row, and `LibraryPage` tests for the new layout, pagination, batch operations, and drawer behavior; verify the targeted desktop test suite passes.
- [x] 4.2 Run the existing frontend test suite and relevant type/lint checks; verify no regressions outside the changed search and folder-list behavior.
