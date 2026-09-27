## Purpose

Provides capabilities for fetching and displaying the exact list of indexed files belonging to a specific folder using the backend's `/api/v1/search` API.

## ADDED Requirements

### Requirement: Querying folder contents dynamically

The folder details view SHALL fetch its file list from the `/api/v1/search` endpoint instead of relying on mock data.

#### Scenario: File list retrieval when folder page is loaded
- **WHEN** the folder details view for a folder with ID `travel-folder` is loaded
- **THEN** the system SHALL send a `POST /api/v1/search` request with `folder_id` set to `travel-folder`, `query` set to `""`, and `categories` containing standard types.

### Requirement: Category filtering within folder

The system SHALL support filtering files within the selected folder by their category (document, image, video).

#### Scenario: User clicks on the Image category pill
- **WHEN** the user selects the "图片" (image) category pill in the folder details view
- **THEN** the system SHALL trigger a new query to `/api/v1/search` with `categories` set to `["image"]` and `folder_id` matching the current folder.

### Requirement: Tag filtering within folder

The system SHALL support filtering files within the selected folder by tags (e.g., "旅游", "攻略").

#### Scenario: User clicks on a tag pill
- **WHEN** the user selects the "旅游" tag pill in the folder details view
- **THEN** the system SHALL trigger a new query to `/api/v1/search` with `tag` set to `旅游` and `folder_id` matching the current folder.
