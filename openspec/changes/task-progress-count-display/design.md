## Context

The tasks table already stores `progress` as an integer percentage alongside `completed_count` and `total_count`. Every current file-processing handler reports both counts, while the import snapshot contract and import dialog only carry and display the percentage. SQLite schema management currently adds missing columns and does not perform destructive column rewrites.

## Goals / Non-Goals

**Goals:**

- Make the completed and total counts the authoritative task-processing progress state.
- Remove percentage progress from the domain, repository, reporting pipeline, and user interfaces.
- Expose one count-based `progress` string while retaining structured counts for progressbar semantics.
- Keep batch import non-blocking and show import progress as completed import items over total items.

**Non-Goals:**

- No migration of progress into a `"3/10"` database string.
- No destructive SQLite migration or physical removal of the legacy `progress` column.
- No change to task scheduling, retries, cancellation, stage order, or SSE transport.
- No waiting for task processing inside batch import.
- No redesign of Tasks page or import dialog visuals.

## Decisions

### Store counts, format at the boundary

The database and domain will retain numeric `completed_count` and `total_count`. `progress` will become a display string assembled at the API boundary as `"{completed}/{total}"`, and structured count fields will remain available for accessibility and progressbar calculation.

Alternative: store `"3/10"` directly in `TaskModel.progress`. Rejected because a string cannot enforce non-negative counts or a positive total, cannot be safely used for width calculation without parsing, and duplicates the normalized columns that already exist.

### Remove percentage from the reporting pipeline

Progress reports will stop carrying a percentage. Handlers will report stage, completed count, and total count. The task entity will update only the count pair and stage; completion will set completed equal to total. UI width will be derived as `completed / total` when the pair is valid.

Alternative: keep percentage internally for the progress bar. Rejected because it preserves two competing progress semantics and allows the displayed count and bar width to disagree.

### Stop using the legacy database column

The ORM model and repository will no longer map or write `TaskModel.progress`. The existing SQLite column remains physically present but dormant, avoiding a table rebuild and preserving rollback safety.

Alternative: alter the column to text or drop it immediately. Rejected because SQLite requires a table rewrite for either operation and neither is needed while counts are authoritative.

### Keep batch import non-blocking

The batch import session will continue to emit `item_completed` immediately after `AddFileUseCase` stores the file and creates the task. It will not poll task status or wait for processing. The import dialog summary will use `(succeeded + failed) / total` and its progressbar will use the same count pair.

Alternative: wait for each task to finish before emitting `item_completed`. Rejected because import success means registration, not background processing completion.

### Handle missing pairs without fabricating data

Queued tasks will show a queued state rather than `0/0`. Processing tasks without a usable pair will show a localized processing indication and an indeterminate progress presentation. Historical completed tasks with a total count will show the full pair; historical tasks without a total count will show their status instead of deriving `45/100`.

Alternative: synthesize `percent/100`. Rejected because it presents a made-up total and loses the requested precision.

## Risks / Trade-offs

- [Risk] The API progress type changes from number to string] -> Update the desktop client and focused contract tests in the same change; document the breaking application-level contract in the proposal.
- [Risk] Existing rows may lack counts] -> Use status-based fallback text and never synthesize a count pair.
- [Risk] A handler forgets the count pair] -> Extend focused handler and progress-reporter tests so processing reports require a positive total and a non-negative completed count.
- [Risk] Dormant database column confuses future maintenance] -> Update model comments and repository tests to state that counts are authoritative.

## Migration Plan

1. Update task progress reporting and the task entity to use count pairs only.
2. Update repository mapping, DTOs, and API schemas to expose count-based `progress` and structured counts.
3. Update import dialog rendering and accessibility values for batch-item counts.
4. Update focused backend and desktop tests.
5. Rollback is limited to restoring the prior model/domain/API mappings and UI fallback logic; no destructive database migration is required.
