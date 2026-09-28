## 1. Navigation and Tag Layout

- [x] 1.1 Change the breadcrumb control to an explicit back button and verify it returns to the folder library.
- [x] 1.2 Move tags to a dedicated row below file type filters and verify all tags stay on one line with horizontal overflow.
- [x] 1.3 Remove the plus-icon add-tag trigger and verify tags are directly selectable from the tag row.

## 2. Pagination and List Layout

- [x] 2.1 Remove the duplicate “共 * 个文件” summary and verify the file total appears only in the pagination footer.
- [x] 2.2 Center pagination controls and right-align the total statistic on the same row, then verify the layout at desktop and narrow widths.
- [x] 2.3 Reorder list columns to “预览、文件名、标签、大小” and center all column headers.

## 3. Validation

- [x] 3.1 Update component tests to cover the back button, tag-row placement, pagination alignment, and list-column order.
- [x] 3.2 Run typecheck, lint, and targeted folder-details tests.
- [ ] 3.3 Visually verify the folder details page with the sidebar expanded and collapsed at desktop and small-screen widths.
