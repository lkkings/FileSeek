## Context

The folder details page keeps selection state in `FolderDetailsView`, but the current list-view row contract does not expose the same selection handlers used by grid cards. Recycle already has a batch API, while moving files between folders is modeled in the backend domain but has no HTTP use case. Tag filters depend on a successful `/library/tags` request and currently degrade to an error-only row.

## Goals / Non-Goals

**Goals:**

- Make grid and list rows share the same selection callbacks and selected-state calculation.
- Route both destructive or location-changing batch actions through explicit confirmation.
- Provide a backend-supported batch move operation and connect it to the folder details UI.
- Move the view toggle into the sort control row.
- Provide a deterministic fallback tag set when the tag request fails.

**Non-Goals:**

- Search-result batch operations.
- Drag-and-drop moving.
- Tag creation or editing.
- Changes to recycle restoration or permanent deletion.

## Decisions

1. **Share selection state at the page level.** `FolderDetailsView` remains the single owner of selected IDs. Grid and list row props both receive the file's selected state, toggle handler, and long-press activation handler. This avoids divergent batch modes and fixes the list-view bug without duplicating state.

2. **Use separate confirmation dialogs.** Recycle reuses the existing destructive confirmation component. Move uses a dialog that lists folders, excludes the current folder, requires a destination, and shows the selected-file count. Both actions disable their confirm buttons while submitting and preserve selection on failure.

3. **Add a batch move endpoint.** Add `POST /api/v1/library/files/move` with `{ "file_ids": string[], "target_folder_id": string }`. A `MoveFilesUseCase` validates that the target exists, loads each file, applies the existing `File.move_to_folder` behavior, saves the files, and adjusts source/destination folder counts. This follows the current feature/use-case/repository structure and avoids adding a new data model.

4. **Treat folder counts as derived consistency, not a query source.** The move use case updates the affected folder counters, while folder listing remains the source for the move dialog. If a count update is interrupted, the next folder query still returns file data; counters can be reconciled later without changing this UI contract.

5. **Place view toggle inside the sort row.** Render the two existing view buttons as the first children of the sort control group, before sort mode and direction. Remove the header view toggle markup so there is only one control location.

6. **Fallback tags are a named constant.** Use `["文档", "图片", "视频"]` with the existing “全部” option. The hook keeps the error and retry capability, while the selector renders the fallback tags instead of an error-only row. This preserves filtering during backend outages without changing the successful tag response.

7. **Refresh after successful operations.** Recycle and move clear selection and call the existing folder contents reload. Success notices include the operation count; failures keep the dialog state so users can retry.

## Risks / Trade-offs

- [Risk] Moving files could partially succeed if one save fails. → Mitigation: wrap repository updates in a transaction where supported, validate all file IDs before mutation, and return one envelope-level success/failure result.
- [Risk] Default tags may not match a user's installed tag vocabulary. → Mitigation: keep them in one frontend constant, continue showing retry, and replace them immediately when the request succeeds.
- [Risk] Long-press behavior can differ by pointer device. → Mitigation: use the existing shared activation mechanism for both row layouts and cover pointer and touch paths in component tests.

## Migration Plan

1. Add the move API contract and backend use case first; it is backward-compatible.
2. Update the frontend API service, folder details state, dialogs, and row props.
3. Add tests for both views, confirmation gating, success/failure handling, sort-row order, and tag fallback.
4. Rollback can remove the frontend call while leaving the new endpoint unused; the existing recycle path is unchanged.
