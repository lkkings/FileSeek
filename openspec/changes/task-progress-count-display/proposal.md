## Why

Task progress currently mixes a coarse percentage with separate completed and total counts. Users see percentages in the import dialog while the Tasks page derives a count ratio, so the same task can appear less precise depending on where it is viewed.

## What Changes

- Treat `completed_count` and `total_count` as the source of truth for task progress.
- **BREAKING** Change the application-level `progress` value from an integer percentage to a `completed_count/total_count` string.
- Remove percentage progress from task reporting and user-facing task surfaces.
- Keep batch import non-blocking: a file is imported successfully once it is stored and its task is created.
- Show import progress as completed batch items over total batch items, not as task-processing progress.
- Define deterministic behavior for tasks that do not yet have a usable count pair, without displaying a fabricated `45/100` percentage ratio.
- Preserve visual progress calculation internally where a ratio is needed for the progress bar width.

## Capabilities

### New Capabilities

- `tasks/progress-display`: Requirements for representing and displaying task progress as completed and total counts across task monitoring surfaces.

### Modified Capabilities

- None.

## Impact

- Affects the Tasks feature domain model, DTOs, repository mapping, progress reporting, scheduler updates, and API schemas.
- Affects the Library import progress snapshot/event contract and the desktop import dialog.
- Affects focused backend and desktop tests for task and import progress.
- No dependency or storage-engine change is planned; existing count columns remain the normalized data source.
