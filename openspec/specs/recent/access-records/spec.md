## Purpose

Provides capabilities for recording file access events, retrieving paginated history of recently accessed files complete with file metadata, and deleting individual file access logs on the platform.

## Requirements

### Requirement: Paginated list of recent access records with file metadata

The system MUST support paginated retrieval of recently accessed file records complete with nested file detail information, ordered by access time in descending order.

#### Scenario: Retrieve first page of recent access records successfully
- **WHEN** a client sends a GET request to `/api/recent` with `page` set to 1 and `page_size` set to 10
- **THEN** the system SHALL return a list containing up to 10 records, each record carrying its unique log ID, access timestamp, and nested file metadata (ID, name, size, category, file type, modified, path, etc.).

### Requirement: Record a new file access event

The system MUST allow clients to log a file access event by providing only the file identifier.

#### Scenario: Log file access successfully
- **WHEN** a client sends a POST request to `/api/recent` with `file_id` set to "file_123"
- **THEN** the system SHALL create a new access record with `file_id` as "file_123" and `accessed_at` set to the current request timestamp, returning a success response.

### Requirement: Delete a recent access record

The system MUST allow clients to delete a specified file access history record by its unique log ID.

#### Scenario: Delete recent access record successfully
- **WHEN** a client sends a DELETE request to `/api/recent/42`
- **THEN** the system SHALL delete the access record with ID 42 and return a success response.
