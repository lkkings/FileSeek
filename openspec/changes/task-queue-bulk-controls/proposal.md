## Why

The Tasks page currently forces users to filter and act on tasks one status at a time, while bulk recovery and cleanup require unsafe frontend loops over only the visible page. The queue needs explicit bulk state transitions that remain correct while the scheduler keeps running.

## What Changes

- Remove status filtering from the desktop Tasks page while retaining the status summary and paginated task list.
- Add a one-click terminate action that changes every incomplete (`queued` and `processing`) task to `cancelled` without stopping the task scheduler.
- Add a one-click continue action that changes every `cancelled` task back to `queued` without stopping or restarting the scheduler.
- Add a one-click delete action that removes every `completed` task record while preserving indexed files.
- Add backend bulk operations so all matching tasks are handled atomically across pagination rather than by frontend loops.
- Keep failed-task retry behavior separate from one-click continue.

## Capabilities

### New Capabilities

- `tasks/task-queue-controls`: Bulk task state transitions, completed-task cleanup, and the Tasks page controls that expose them.

### Modified Capabilities

- None.

## Impact

- Affects `desktop/src/pages/tasks/TasksPage.tsx`, `desktop/src/features/tasks/hooks/useTasks.ts`, `desktop/src/services/api/tasks.ts`, and focused Tasks tests.
- Affects backend task manager, repository, use cases, HTTP routes, dependency assembly, and focused backend tests.
- Does not change the scheduler lifecycle: it must remain accepting and running during both bulk operations.
- Does not delete completed files, file chunks, or vector index data.
