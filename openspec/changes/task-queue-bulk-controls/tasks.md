## 1. Backend Bulk Operations

- [x] 1.1 Add transactional repository operations for cancelling incomplete tasks, continuing cancelled tasks, and deleting completed tasks, and verify focused repository tests cover multi-page and concurrent-state cases.
- [x] 1.2 Add manager-level bulk operations that register cancellation signals for processing tasks and wait for cancellation cleanup before continuing tasks, and verify manager tests prove the scheduler is never paused or stopped.
- [x] 1.3 Add scheduler-safe cancellation coordination and verify a focused scheduler test shows a delayed cancellation cannot overwrite a task transitioned back to queued.

## 2. Backend API

- [x] 2.1 Add bulk operation use cases, response schemas, mappers, routes, and dependency wiring for cancel-incomplete, continue-cancelled, and delete-completed, and verify API contract tests cover success, empty, and error cases.
- [x] 2.2 Verify each bulk endpoint returns the affected task count and does not alter failed, completed, or unrelated task statuses.

## 3. Frontend Integration

- [x] 3.1 Add typed API functions and hook mutations for the three bulk operations, and verify hook tests cover request paths and task-list invalidation.
- [x] 3.2 Remove status filtering from `useTasks` and verify the hook requests the unfiltered task list.

## 4. Tasks Page UI

- [x] 4.1 Remove the status filter controls and state while preserving the status summary and pagination, and verify Tasks page tests no longer query status filter buttons.
- [x] 4.2 Add localized one-click terminate, continue, and delete-completed controls with count-based disabled states and success/error notices, and verify Tasks page tests exercise each action.
- [x] 4.3 Update feature-local styles and accessibility semantics for the new toolbar controls, and verify keyboard roles, names, and disabled states remain testable.

## 5. Validation

- [x] 5.1 Run focused backend tests for task bulk operations and verify all pass.
- [x] 5.2 Run focused frontend tests for the Tasks page and task hook, and verify all pass.
- [x] 5.3 Run typecheck, lint, and production build, and verify no new warnings related to this change.
