## 1. Domain and Persistence

- [x] 1.1 Update task progress reporting to carry only stage, completed count, and total count; reject invalid count pairs; and verify focused task progress-reporter and scheduler tests pass.
- [x] 1.2 Update document, video, and image handlers to report their existing count pairs without percentage arguments, and verify their focused handler tests pass.
- [x] 1.3 Remove the legacy percentage field from task domain mapping and repository persistence while retaining the physical SQLite column, and verify repository tests no longer read or write it.
- [x] 1.4 Map tasks to a count-based `progress` string plus structured completed and total counts, including completion and missing-pair fallback behavior, and verify focused backend DTO and API tests pass.

## 2. Import Progress Behavior

- [x] 2.1 Keep batch import non-blocking and emit item completion after file storage and task creation, and verify focused batch-import and API stream tests pass.
- [x] 2.2 Remove task-processing progress from the import event contract, and verify the import stream no longer depends on task status polling.

## 3. Desktop Progress Display

- [x] 3.1 Update desktop task API types and normalization to accept the count-based `progress` string and structured counts, and verify focused type-dependent task tests pass.
- [x] 3.2 Update Tasks page rows to render exact `completed/total` text, count-derived bar width, and non-fabricated fallback text, and verify Tasks page and TaskRowItem tests pass.
- [x] 3.3 Update the import dialog to render completed batch items over total items without task-processing progress, and verify focused ImportFileDialog tests pass.

## 4. Validation

- [x] 4.1 Run the focused backend suite for task progress, repositories, handlers, tasks API, and batch import, and verify all targeted tests pass.
- [x] 4.2 Run focused desktop Tasks page, TaskRowItem, and ImportFileDialog tests, and verify all targeted tests pass.
- [x] 4.3 Run backend lint/typecheck and desktop typecheck/lint/build checks, and verify no new failures or warnings related to this change.
- [ ] 4.4 Manually inspect a processing task and an import task, and verify both surfaces display the same exact `completed/total` value with accessible progressbar semantics.
