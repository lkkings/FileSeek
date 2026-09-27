## 1. API Contracts

- [x] 1.1 Update Recent, Recycle, and Tasks service interfaces to match backend field names and verify `pnpm typecheck` passes
- [x] 1.2 Add optional DELETE body support to the API client and verify a focused service test confirms the serialized request path and body
- [x] 1.3 Correct Recent and Recycle endpoint paths and request payloads and verify focused service tests match the OpenAPI routes

## 2. Recent Access

- [x] 2.1 Update `useRecentAccess` to return backend pagination data and UI-mapped file rows while retaining record IDs and verify unit behavior covers empty and nested-file responses
- [x] 2.2 Add a Recent mutation hook for recording access and verify a test confirms one `POST /api/v1/recent` request with `{ file_id }`
- [x] 2.3 Implement Recent multi-select, long-press selection, sequential record deletion with partial-failure handling, and pagination in `RecentPage` and verify interaction tests cover selection and deletion refresh
- [x] 2.4 Refactor `FileDetailDrawer` to invoke an open callback instead of calling the Recent service and verify a test confirms the callback receives the selected file

## 3. Recycle Bin

- [x] 3.1 Add typed `RecycleRowItem` selection and long-press behavior using existing result-row styles and verify component tests cover row selection and checked state
- [x] 3.2 Add Recycle list, restore, and permanent-delete mutations with query invalidation and verify tests confirm exact request bodies and cache refresh
- [x] 3.3 Wire Recycle pagination, multi-select, restore, and permanent-delete confirmation in `RecyclePage` and verify interaction tests cover both actions and partial error notices
- [x] 3.4 Pass a shared move-to-recycle callback from pages into search results and folder details and verify tests confirm both views send selected `file_ids` and refresh their own data

## 4. Tasks

- [x] 4.1 Update `useTasks` for the exact task response, typed status filter, counts, pagination, retry mutation, and 2-second polling and verify hook tests cover request parameters and invalidation
- [x] 4.2 Add typed `TaskRowItem` with status, progress, current stage, error, and retry action using existing visual classes and verify component tests cover all four statuses
- [x] 4.3 Wire task status filtering, counts, pagination, retry, and notices in `TasksPage` and verify interaction tests reject the invalid `pending` value and exercise retry

## 5. Visual, i18n, And Validation

- [x] 5.1 Add Lingui translations for every new user-visible string and verify no hardcoded UI text remains in new components
- [x] 5.2 Add narrowly scoped Recycle and Task row styles matching existing typography, colors, spacing, and responsive behavior and verify visual inspection at desktop, 1024px, 780px, and 480px widths
- [x] 5.3 Run `pnpm typecheck`, `pnpm lint`, and `pnpm test` and verify all commands pass
- [x] 5.4 Start the Vite development server, exercise Recent, Recycle, and Tasks against the backend or test transport, and verify pagination, mutations, notices, and responsive layouts work as specified
