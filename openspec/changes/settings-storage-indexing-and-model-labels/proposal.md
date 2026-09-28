## Why

The settings page currently stores model-label and storage-drive data only in browser localStorage, so the backend cannot use those preferences when files are indexed or read. File indexing also copies local files into the library root, which conflicts with the intended product behavior: FileSeek should record an index and read the original file through its configured source.

## What Changes

- Add backend-managed model-label vocabulary for document, image, and video classification.
- Add backend-managed storage locations, including the built-in `local` location and multiple NAS locations.
- Change file registration to index the original source instead of copying or moving local files.
- Bind each indexed file to its source storage location and preserve the original source path.
- Resolve previews, thumbnails, and background processing through the file's source storage location.
- Mark files unavailable when their source storage is deleted or the original file cannot be accessed; retain the index record.
- Update the settings UI to load and save labels and storage locations through the backend API.
- Keep UI locale preference local to the desktop client.
- Keep model-label vocabulary independent from existing file tags and `file_tags`.

## Capabilities

### New Capabilities

- `settings/classifier-labels`: Manage the document, image, and video label vocabulary used by the model classifier.
- `settings/storage-locations`: Manage built-in local and user-defined NAS storage locations, including soft deletion and connection testing.
- `library/file-indexing`: Register file indexes without copying source files, bind them to storage locations, and track source availability.
- `library/file-source-access`: Resolve indexed files through their bound storage location for preview, thumbnail, and background processing.

### Modified Capabilities

- None.

## Impact

- Backend settings feature and HTTP routes.
- Desktop settings provider, services, and `SettingsPageView`.
- `AddFileCommand`, `AddFileUseCase`, file entities, and file HTTP schemas.
- File repository and database models for storage binding and availability.
- File preview, thumbnail, and task-processing read paths.
- Classifier label provisioning so label updates affect subsequent classification tasks.
- API tests for settings, indexing, unavailable sources, and credential redaction.
