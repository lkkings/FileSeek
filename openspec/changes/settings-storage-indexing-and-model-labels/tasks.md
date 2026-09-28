## 1. Data Model and Persistence

- [x] 1.1 Add storage-location and classifier-label database models with unique and status constraints; verify schema initialization creates the expected tables in an isolated SQLite test.
- [x] 1.2 Add file source-binding and availability columns, including storage identifier, access state, and last-checked time; verify migration adds the columns to an existing `files` table.
- [x] 1.3 Implement settings repositories for storage locations and classifier labels; verify unit tests cover creation, update, soft delete, listing, and redacted credentials.
- [x] 1.4 Seed the protected local location, system external location, and default classifier labels; verify startup seeding is idempotent and does not overwrite user changes.
- [x] 1.5 Backfill existing file bindings by path type and preserve legacy paths; verify repository tests cover library-root, absolute-local, and HTTP/HTTPS records.

## 2. Settings Backend

- [x] 2.1 Create classifier-label domain entities, commands, queries, DTOs, and use cases; verify a use-case test rejects duplicate category labels and leaves stored labels unchanged.
- [x] 2.2 Create storage-location domain entities, commands, queries, DTOs, and use cases; verify use-case tests cover create, update, list, protected local deletion, and NAS soft deletion.
- [x] 2.3 Implement storage-location connection testing for local and mounted NAS paths plus protocol reachability checks; verify tests cover successful and failed connections without exposing credentials.
- [x] 2.4 Implement soft deletion that marks bound files unavailable and returns the affected count; verify an integration test retains file indexes after deleting a NAS location.
- [x] 2.5 Add settings HTTP schemas, mappers, routes, dependencies, and app router registration; verify API tests cover all classifier-label and storage-location endpoints.
- [x] 2.6 Verify storage-location API responses never include passwords and invalid requests return envelope errors without partial updates.

## 3. Source Access Infrastructure

- [x] 3.1 Define the application source-access port for metadata, hash reads, byte-range reads, and content opening; verify the port contract is covered by fake-based use-case tests.
- [x] 3.2 Implement local, legacy external URI, and mounted-NAS adapters behind a storage resolver; verify adapter tests resolve absolute, URI, and mounted-root source paths.
- [x] 3.3 Add repository methods for availability updates and bulk unavailable marking; verify tests record access state and last-checked time while retaining source bindings.

## 4. Index-Only File Registration

- [x] 4.1 Extend file registration commands and HTTP requests with a storage location identifier while preserving the existing path field as the source path; verify request mapping defaults omitted identifiers to `local`.
- [x] 4.2 Rewrite file registration to validate the active source, stream content identity, detect file type, and capture metadata without writing to the library root; verify no library copy is created.
- [x] 4.3 Preserve duplicate-content behavior and save source coordinates, category, folder, and availability state; verify duplicate registration does not create a second file record.
- [x] 4.4 Create processing tasks with a classifier-label snapshot and short-lived source cache metadata; verify task metadata retains the label version and temporary cache path.

## 5. Classifier Vocabulary Integration

- [x] 5.1 Implement a versioned classifier-label provider and classifier cache keyed by label-set version; verify changed vocabularies produce a new classifier instance and unchanged vocabularies reuse the cache.
- [x] 5.2 Update document, image, and video handlers to classify with the task's captured label snapshot; verify in-flight tasks keep their original vocabulary when settings change.
- [x] 5.3 Confirm existing file tags and `file_tags` associations remain unchanged after vocabulary replacement; verify a persistence test around label removal.

## 6. Source-Based Reads and Processing

- [x] 6.1 Route file previews through the source resolver and preserve Range support; verify API tests return full and partial content from local and mounted-NAS sources.
- [x] 6.2 Route thumbnail generation through the source resolver; verify image and video thumbnail tests use the bound source and retain the index when access fails.
- [x] 6.3 Update task processors to read from the bound source or its temporary cache and clean up cache files after completion; verify processing does not create permanent library copies.
- [x] 6.4 Mark files unavailable on source or storage access failure and return a distinct unavailable response; verify preview failure retains the index and records the check time.
- [x] 6.5 Add an explicit file availability-check action that revalidates an unavailable source and restores availability when readable; verify recovery and continued-unavailable outcomes.

## 7. Desktop Settings Integration

- [x] 7.1 Add typed frontend API services for classifier labels and storage locations; verify API contract tests cover request and response mapping.
- [x] 7.2 Replace localStorage persistence for labels and storage locations with backend queries and mutations while keeping locale local; verify provider tests load and save backend data.
- [x] 7.3 Update settings components to use backend state, accept write-only credentials, and show deletion consequences for bound files; verify UI tests cover successful and failed mutations.
- [x] 7.4 Remove fabricated NAS capacity display or populate it only from real capacity data; verify settings tests do not assert mocked default capacities.
- [x] 7.5 Update any file-registration UI or request builder to select an active storage location; verify the request includes the selected identifier and defaults to local when omitted.

## 8. Validation and Documentation

- [x] 8.1 Add or update backend API and use-case tests for settings, index-only registration, unavailable sources, credential redaction, and classifier snapshots; verify targeted pytest suites pass.
- [x] 8.2 Run backend formatting, lint, type checking, and tests; verify `uv run ruff`, `uv run mypy`, and `uv run pytest` pass or record only pre-existing unrelated failures.
- [x] 8.3 Run desktop tests and production build; verify `npm run test` and `npm run build` pass or record only pre-existing unrelated failures.
- [x] 8.4 Validate the OpenSpec change and review the final diff; verify `openspec validate settings-storage-indexing-and-model-labels --strict` passes.
