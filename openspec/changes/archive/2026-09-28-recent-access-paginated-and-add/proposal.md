## Why

Currently, the recent access feature only supports static `limit` query parameters without pagination, returning basic file IDs which leaves the frontend unable to display file metadata without secondary HTTP requests. Additionally, clients need a way to dynamically add recent access entries and delete access history records to keep their recent documents panel up to date and clean. Upgrading this module with a paginated list returning full file metadata, dynamic access logging, and a delete record endpoint solves these requirements.

## What Changes

- **Paginated Recent Access with File Details**: Upgrade `GET /recent` to support `page` and `page_size` parameters. Return access logs, each with full file details (`FileResponse`) by calling standard services, preventing the "N+1" loading issue in the frontend.
- **Dynamic Access Logging**: Expose a `POST /recent` endpoint accepting `file_id` to add recent access logs on the fly.
- **Delete Access Log Entry**: Add a `DELETE /recent/{record_id}` endpoint to remove specified records from access history.

## Capabilities

### New Capabilities
- `recent/access-records`: Defines the specification for creating, paginated listing with nested file information, and deleting recent access records.

### Modified Capabilities

## Impact

- **Recent Feature Layer**:
  - Updates `RecentAccessRepository` domain port to support paginated list and deletion.
  - Refactors `RecentAccessDTO` to support optional nested `FileDTO`.
  - Introduces `DeleteRecentAccessUseCase` and updates `ListRecentAccessUseCase` & `RecordAccessUseCase`.
  - Updates routing mappings to cleanly convert DTOs to Schema Responses.
  - Defines `GET /recent`, `POST /recent`, and `DELETE /recent/{record_id}` endpoints.
- **Composition Root**:
  - Injects `file_repo` into recent use cases and registers `DeleteRecentAccessUseCase` dependency.
