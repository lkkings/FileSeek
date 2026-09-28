## Context

The desktop settings page currently persists labels and drives in localStorage. The backend has no active settings feature, `AddFileUseCase` writes local files into the configured library root, and preview code opens the stored path directly. The new behavior must preserve source files, support multiple source locations, and keep classifier vocabulary separate from file tags.

## Goals / Non-Goals

**Goals:**

- Persist classifier labels and storage locations in the backend database.
- Register file indexes without copying or moving source files.
- Bind every new file index to a source storage location.
- Route preview, thumbnail, and task reads through that source location.
- Preserve indexes when their source becomes unavailable.
- Keep the settings UI responsive to backend state while retaining locale as a local UI preference.

**Non-Goals:**

- Copying, moving, migrating, or deduplicating physical files between storage locations.
- Managing or validating file tags already assigned to files.
- Implementing full SMB, NFS, or WebDAV clients in this change.
- Changing the current task scheduler or vector-index format.
- Synchronizing settings across multiple users or devices.

## Decisions

### Storage locations are source catalogs

`StorageLocation` identifies where an indexed file lives. It is not a copy destination. The built-in `local` location is seeded on startup, protected from deletion, and used when a registration request omits `storage_id`.

Initial NAS support uses a mounted filesystem path. A NAS location stores a stable identifier, display name, protocol, and root or endpoint. SMB, NFS, and WebDAV metadata can be saved and tested for basic reachability, but source reads in this change require a locally mounted NAS path. Protocol-specific adapters can be added later behind the same resolver port.

This avoids blocking the indexing model on userspace protocol clients while making storage identity and file bindings stable.

### File indexes store source coordinates

The file domain model changes from a single `path` concept to:

- `storage_id`: stable source-location identifier.
- `source_path`: the original path semantics for that location.
- `access_state`: `available`, `unavailable`, or `unknown`.
- `last_checked_at`: time of the last source accessibility check.

For compatibility with existing code and databases, the current database `path` column remains the persistence column for `source_path`; repository mappers expose it under the source-path name. Existing absolute local paths are bound to `local`. Existing HTTP and HTTPS indexes can retain URI resolution through a system-managed external source during migration.

The source path semantics are storage-specific:

- `local`: an absolute local path.
- mounted NAS: a path relative to the configured mounted root.
- external legacy URI: the original HTTP or HTTPS URI.

### Source access is behind an application port

Library use cases depend on a source-access port rather than constructing concrete filesystem paths. The port supports metadata reads, byte-range reads, and opening source content for preview and processing. An infrastructure resolver implements the port by loading the active `StorageLocation` and dispatching to the matching adapter.

This keeps `AddFileUseCase`, preview, and task processing independent from NAS protocol details and allows adapters to evolve without changing application contracts.

### Registration hashes and detects without permanent copies

Registration reads the original source to calculate the content hash, detect the supported file type, and capture size and modification time. It may create a short-lived temporary file for processors that require seekable input, but that file is cleanup-only cache and never becomes the indexed copy.

The existing global content-hash identity remains. If the same content is already indexed, registration reports a duplicate instead of creating a second record.

### NAS deletion is a soft delete

Deleting a NAS location sets its status to deleted, omits it from active lists, and marks all bound file indexes unavailable. The location row and file bindings remain so a future reactivation can restore access. The built-in local location cannot be deleted.

Source read failures also mark the file unavailable and record the check time. Index records and file metadata remain available for search and listing.

### Classifier labels use a versioned vocabulary

Labels are stored in a dedicated table keyed by category and label, and have no relationship to `TagModel`, `file_tags`, or file entities. The settings API replaces the full vocabulary.

The classifier receives a label-set snapshot keyed by a stable vocabulary version. New tasks capture the current version when they are created; in-flight tasks continue with their captured snapshot. Classifier instances are cached by version so repeated label updates do not force unrelated tasks to re-embed unchanged labels.

### Settings API is split by concern

Classifier vocabulary uses `GET /api/v1/settings/classifier-labels` and `PUT /api/v1/settings/classifier-labels`.

Storage locations use:

- `GET /api/v1/settings/storage-locations`
- `POST /api/v1/settings/storage-locations`
- `PUT /api/v1/settings/storage-locations/{id}`
- `DELETE /api/v1/settings/storage-locations/{id}`
- `POST /api/v1/settings/storage-locations/{id}/test`

Storage responses redact passwords. Credentials are accepted on create and update but never returned. The settings UI uses backend queries and mutations for labels and locations; locale remains in local storage.

## Risks / Trade-offs

- [Risk] Mounted-path NAS does not satisfy users expecting direct SMB, NFS, or WebDAV reads. -> The resolver and storage model support later protocol adapters without changing file bindings or APIs.
- [Risk] Marking a file unavailable after one failure can hide a transient network outage. -> Store `last_checked_at` and expose an explicit availability check so recovery can be re-evaluated without deleting the index.
- [Risk] The classifier must re-embed a changed vocabulary. -> Cache classifiers by vocabulary version and only rebuild when the label set changes.
- [Risk] Source files can change after indexing, so content identity and index metadata can diverge. -> Recalculate identity at registration; future revalidation can compare metadata and update availability.
- [Risk] Stored NAS credentials are sensitive. -> Redact all read responses, avoid logging secrets, and restrict API writes. Longer term, move credentials to an OS-backed secret store.
- [Risk] Existing files already copied into the library root cannot be undone safely. -> Migrate their bindings to `local` and continue reading their existing path; do not delete physical files during this change.

## Migration Plan

1. Add `storage_locations` and `classifier_labels` tables through the existing schema initialization.
2. Add nullable `storage_id`, `access_state`, and `last_checked_at` columns to `files`, then backfill them after schema creation.
3. Seed the built-in `local` location and a non-user-manageable external location for legacy HTTP and HTTPS paths.
4. Bind existing local and library-root paths to `local`; bind legacy URI paths to external.
5. Seed classifier labels from the current environment defaults when no database vocabulary exists.
6. Switch registration and source reads to the new bindings.
7. Update the settings UI to call the backend and stop persisting labels or storage drives in localStorage.

Rollback keeps existing file paths intact. The new nullable columns and tables can remain unused if the previous registration and preview paths are restored.
