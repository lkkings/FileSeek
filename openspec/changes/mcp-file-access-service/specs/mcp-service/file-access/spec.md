## Purpose

Provides MCP-compatible tools for AI assistants to access FileSeek's file library: list folders, search files, and read file contents with user-controlled permission grants.

## ADDED Requirements

### Requirement: List folders without authorization

The MCP Server SHALL expose a `list_folders` tool that returns all folders from the FileSeek library without requiring user authorization.

#### Scenario: Successful folder listing
- **WHEN** an MCP client calls `list_folders()`
- **THEN** the system returns a list of all folders with their id, name, and file count

#### Scenario: Backend unavailable
- **WHEN** FileSeek Backend is not running
- **THEN** the tool returns an error indicating Backend is unavailable and suggests starting FileSeek Desktop

### Requirement: Search files without authorization

The MCP Server SHALL expose a `search_files` tool that searches the FileSeek library without requiring user authorization.

#### Scenario: Successful search with results
- **WHEN** an MCP client calls `search_files(query="报告")`
- **THEN** the system returns matching files with id, name, path, score, and folder information

#### Scenario: Search with filters
- **WHEN** an MCP client calls `search_files(query="照片", folder_id="personal", file_types=["jpg", "png"])`
- **THEN** the system returns only matching image files from the specified folder

#### Scenario: Empty search results
- **WHEN** a search query matches no files
- **THEN** the system returns an empty list with total count of 0

### Requirement: Read file requires authorization

The MCP Server SHALL require user authorization before reading file contents via the `read_file` tool.

#### Scenario: Read file without authorization
- **WHEN** an MCP client calls `read_file(file_id="abc")` and no valid grant exists
- **THEN** the system returns a permission error with file details and available authorization options

#### Scenario: Read file with valid file grant
- **WHEN** a file has been granted access for 10 minutes
- **THEN** `read_file()` for that file succeeds without prompting until the grant expires

#### Scenario: Read file with valid folder grant
- **WHEN** a folder has been granted access
- **THEN** `read_file()` for any file in that folder succeeds without prompting until the grant expires

#### Scenario: Expired grant
- **WHEN** an MCP client calls `read_file()` and the grant has expired
- **THEN** the system returns a permission error as if no grant existed

### Requirement: Read document by page and chunk range

The MCP Server SHALL support reading document files (PDF, Word, etc.) by specifying page number and chunk range.

#### Scenario: Read specific chunks from a page
- **WHEN** an MCP client calls `read_file(file_id="abc", page=5, chunk_start=10, chunk_end=25)`
- **THEN** the system returns text content from chunks 10-25 on page 5

#### Scenario: Read entire page
- **WHEN** an MCP client calls `read_file(file_id="abc", page=5)` without chunk range
- **THEN** the system returns all chunks from page 5

#### Scenario: Read entire document
- **WHEN** an MCP client calls `read_file(file_id="abc")` without page or chunk parameters
- **THEN** the system returns all content from the document (subject to reasonable size limits)

### Requirement: Read image as Base64

The MCP Server SHALL return image files as Base64-encoded data.

#### Scenario: Read image file
- **WHEN** an MCP client calls `read_file(file_id="xyz")` for an image file with valid authorization
- **THEN** the system returns Base64-encoded image data with MIME type

### Requirement: Video files not supported

The MCP Server SHALL return an error when attempting to read video files.

#### Scenario: Attempt to read video
- **WHEN** an MCP client calls `read_file(file_id="video123")` for a video file
- **THEN** the system returns an error indicating video files are not supported via MCP

### Requirement: Grant file access

The MCP Server SHALL expose a `grant_file_access` tool that authorizes reading a specific file for a duration.

#### Scenario: Grant access to a file
- **WHEN** an MCP client calls `grant_file_access(file_id="abc", duration_minutes=10)`
- **THEN** the system records the grant with expiration timestamp and persists it to disk

#### Scenario: Grant overwrites existing grant
- **WHEN** a file already has a grant and a new grant is issued
- **THEN** the system replaces the old grant with the new one

### Requirement: Grant folder access

The MCP Server SHALL expose a `grant_folder_access` tool that authorizes reading all files in a folder for a duration.

#### Scenario: Grant access to a folder
- **WHEN** an MCP client calls `grant_folder_access(folder_id="work_docs", duration_minutes=10)`
- **THEN** the system records the grant for all files in that folder and persists it to disk

#### Scenario: New files added to granted folder
- **WHEN** a folder has an active grant and new files are added to it
- **THEN** those new files are automatically covered by the existing grant

### Requirement: Grants persist across MCP Server restart

The MCP Server SHALL load grants from disk on startup and preserve unexpired grants.

#### Scenario: MCP Server restart with active grants
- **WHEN** MCP Server is restarted while grants are still valid
- **THEN** the grants remain active and files/folders can be read without re-authorization

#### Scenario: Expired grants cleaned on load
- **WHEN** MCP Server loads grants from disk
- **THEN** any grants with expiration in the past are discarded

### Requirement: Dynamic token from connection file

The MCP Server SHALL read API token dynamically from FileSeek's connection file on each request.

#### Scenario: Backend restart generates new token
- **WHEN** FileSeek Backend restarts and writes a new token to connection.json
- **THEN** MCP Server automatically uses the new token on the next API call

#### Scenario: Connection file not found
- **WHEN** connection.json does not exist or is unreadable
- **THEN** MCP Server returns an error indicating Backend is not running

#### Scenario: Token cached until file changes
- **WHEN** connection.json has not been modified
- **THEN** MCP Server uses the cached token without re-reading the file
