## 1. Backend Batch Move API

- [x] 1.1 Add the move-files command, request/response schemas, use case, dependency wiring, and `POST /api/v1/library/files/move` route; verify `cd backend && uv run pytest tests/api/test_library.py` passes with new route tests.
- [x] 1.2 Validate that all file IDs and the target folder exist before mutation and keep folder counts consistent after a successful move; verify focused use-case/API tests cover missing files, missing targets, and successful moves.

## 2. Folder Details Selection and Operations

- [x] 2.1 Extend list rows with the same selected-state, toggle, and long-press props used by grid cards while keeping `FolderDetailsView` as the selection owner; verify list-view selection and view-switch persistence tests pass.
- [x] 2.2 Gate batch recycle behind the confirmation dialog, clear selection and reload only after success, and retain selection on failure; verify the existing folder-details recycle test covers confirmation and add failure coverage.
- [x] 2.3 Add the move-to-folder confirmation dialog, destination loading/exclusion, submitting state, success refresh, and failure retention; verify component tests cover target choice, confirmation, success, and failure.

## 3. Controls and Tag Fallback

- [x] 3.1 Move the grid/list view toggle to the first position in the sort control row and remove the header toggle; verify the rendered control order and absence of the header toggle by test.
- [x] 3.2 Add the named default tag set to the tag-list failure path while preserving retry and successful API tags; verify `TagFilterSelector` and `useLibraryTags` tests cover fallback and recovery.

## 4. Integration Verification

- [x] 4.1 Add frontend API-client coverage for the move endpoint payload and envelope handling; verify `cd desktop && npm run test -- src/services/api/api-contracts.test.ts` passes.
- [ ] 4.2 Run `cd desktop && npm run typecheck`, `cd desktop && npm run test`, and `cd backend && uv run pytest`; verify all configured checks pass.
