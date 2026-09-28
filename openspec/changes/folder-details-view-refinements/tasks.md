## 1. Backend Tag List API

- [x] 1.1 Add a tag-list endpoint under the library API and verify it returns distinct tags from the database.
- [x] 1.2 Add API contract tests for success, empty-list, and failure responses and verify the backend test suite passes.

## 2. Folder Details Data and Search

- [x] 2.1 Add a desktop API service and feature hook for the tag-list endpoint and verify request/error handling in tests.
- [x] 2.2 Replace the advanced-filter button with the search icon toggle and verify it opens and closes the existing `SearchBar`.
- [x] 2.3 Keep folder search scoped to the current folder and verify submitted search requests include the folder ID.

## 3. Tag Selection and Layout

- [x] 3.1 Move tag chips beside the file-type filters and add the add-tag popover trigger.
- [x] 3.2 Load backend tags into the popover, support selection and retry on failure, and verify the selected tag filters the file query.
- [ ] 3.3 Place the file-count summary and sort control in one right-aligned row and verify the layout in the desktop preview.

## 4. Responsive File List and Pagination

- [x] 4.1 Refactor the list view to show preview, tags, file name, and size only.
- [ ] 4.2 Add responsive rules for sidebar-expanded one-column and sidebar-collapsed two-column small-screen layouts and verify both states visually.
- [x] 4.3 Replace custom pagination markup with the shared `Pagination` component and verify page changes request the correct page.

## 5. File Interactions

- [x] 5.1 Open the existing `FileDetailDrawer` on single click and verify the drawer shows the selected file.
- [x] 5.2 Open the file preview on double click and verify the preview callback receives the selected file.

## 6. Validation

- [x] 6.1 Add or update component tests for search toggling, tag selection, responsive list rendering, pagination, and file interactions.
- [ ] 6.2 Run typecheck, lint, and targeted frontend/backend tests and verify all checks pass.
- [ ] 6.3 Manually verify the folder details page with the sidebar expanded and collapsed at desktop and small-screen sizes.
