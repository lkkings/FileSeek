## Context

The task queue already supports single-task retry, cancel, and delete, and the scheduler runs continuously while accepting queued work. Bulk controls must therefore coordinate with the scheduler without changing its lifecycle. See `proposal.md` for motivation and `specs/tasks/task-queue-controls/spec.md` for the behavior contract.

## Goals / Non-Goals

**Goals:**

- Provide atomic bulk transitions for incomplete, cancelled, and completed tasks.
- Keep the scheduler running and accepting work throughout every bulk operation.
- Prevent a bulk continue operation from racing with in-flight cancellation cleanup.
- Remove status filtering from the Tasks page without losing the status summary.

**Non-Goals:**

- No scheduler pause, resume, stop, or restart.
- No breakpoint resume for partially processed tasks.
- No changes to failed-task retry semantics.
- No deletion of indexed files, chunks, or vector data.

## Decisions

### Use backend bulk operations

The backend will expose action endpoints for bulk cancel, bulk continue, and bulk delete. The frontend will call one endpoint per action rather than looping over visible tasks.

Alternative: loop single-task APIs from the frontend. Rejected because it only covers the current page, creates partial failures, and cannot coordinate with scheduler-owned processing tasks.

### Define incomplete as queued or processing

One-click terminate will transition only `queued` and `processing` tasks to `cancelled`. Failed tasks remain failed because retry already covers them, and completed tasks remain completed.

Alternative: include failed tasks. Rejected because it would overlap with the existing retry action and make the two controls ambiguous.

### Keep the scheduler accepting work

Bulk operations will not call `stop_accepting()`, `stop()`, or `shutdown()`. The scheduler continues running and may claim new work as soon as the bulk transaction commits.

Alternative: pause claiming during bulk cancel. Rejected because the user explicitly requires the queue to remain active.

### Coordinate continue with cancellation cleanup

One-click terminate will register cancellation signals for processing tasks and persist their terminal state. One-click continue will wait until those cancellation signals are cleared before requeueing cancelled tasks. This prevents the scheduler from overwriting a newly queued task with a delayed cancelled state.

Alternative: requeue immediately and rely on timing. Rejected because it can lose the continue update.

### Use action-style HTTP routes

Use explicit action routes:

- `POST /tasks/cancel-incomplete`
- `POST /tasks/continue-cancelled`
- `POST /tasks/delete-completed`

Each response returns the number of affected tasks. This avoids ambiguity with the existing single-task DELETE route.

Alternative: `DELETE /tasks/completed`. Rejected because it can be confused with the existing `/{task_id}` path and is less explicit about the bulk action.

### Reuse retry semantics for continue

One-click continue will move cancelled tasks back to `queued` and clear prior progress, matching existing retry behavior. This ensures a continued task starts a clean processing run after cancellation cleanup.

Alternative: preserve partial progress. Rejected because cancelled tasks have already had partial results cleaned up and the system does not currently support breakpoint resume.

## Risks / Trade-offs

- [Risk] Bulk cancel can race with the scheduler claiming a queued task] -> Use transactional status updates and include any task that becomes processing before the bulk transaction commits.
- [Risk] One-click continue can race with delayed cancellation cleanup] -> Wait for cancellation signals to clear before requeueing.
- [Risk] A long-running cancellation could delay the continue response] -> Wait for cancellation cleanup to finish; if coordination times out, fail the operation without partially requeueing tasks.
- [Risk] Removing filters could make a specific status harder to find] -> Retain the status summary and clear bulk-action affordances for each state.

## Migration Plan

1. Add repository and manager bulk operations with scheduler-safe coordination.
2. Add use cases, routes, schemas, and dependency wiring.
3. Add frontend API functions, hook mutations, and Tasks page controls.
4. Remove status filter state and UI.
5. Add focused backend and frontend tests.
6. Roll back is limited to task bulk control code and Tasks page control code; no data migration is required.
