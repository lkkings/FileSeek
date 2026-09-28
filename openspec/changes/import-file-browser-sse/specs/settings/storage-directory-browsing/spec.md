## Purpose

Provides a storage-aware directory listing API so the import dialog can navigate readable local filesystem paths and mounted-NAS sources without exposing NAS files outside their configured roots.

## ADDED Requirements

### Requirement: List directory entries for a storage location
The system SHALL list the immediate child directories and supported files for an active storage location and requested directory path. Supported files MUST be limited by filename suffix to document, image, and video formats. Each returned entry MUST include its display name, kind, source path, size, and modified time.

#### Scenario: Browse a local storage directory
- **WHEN** a client requests entries for the active local storage location and a readable local directory
- **THEN** the system returns the immediate child directories and files with their source paths and metadata

#### Scenario: Browse a mounted NAS directory
- **WHEN** a client requests entries for an active mounted-NAS storage location and a readable directory inside its configured root
- **THEN** the system returns the immediate child directories and files with source paths that can be used for import

#### Scenario: Filter unsupported files
- **WHEN** a requested directory contains files whose suffixes are not recognized document, image, or video formats
- **THEN** the system omits those files while retaining child directories and supported files

#### Scenario: Request a missing directory
- **WHEN** a client requests a directory that does not exist or is not readable
- **THEN** the system returns a source-unavailable error and does not return a partial listing

### Requirement: Support an explorer-style current path
The system SHALL return the resolved current directory path with every directory listing. For the local storage location, an empty requested path MUST default to the current operating system's user home directory. The import dialog SHALL provide parent-directory navigation and direct path-entry navigation.

#### Scenario: Request an empty path
- **WHEN** a client requests the system local storage with an empty path
- **THEN** the system lists the current operating system's user home directory and returns that resolved path

#### Scenario: Return to the parent directory
- **WHEN** the user activates parent-directory navigation and the current directory has a parent
- **THEN** the import dialog requests the current directory's parent and displays the resolved current path

#### Scenario: Paste a path
- **WHEN** the user pastes a readable local path or a mounted-NAS path inside its root and submits the path field
- **THEN** the import dialog requests that path directly and displays the resolved current path

### Requirement: Restrict mounted-NAS browsing to its root
The system MUST reject mounted-NAS directory requests that resolve outside the storage location's configured root, including parent traversal and symbolic-link escapes. Local storage SHALL allow readable local filesystem paths and MUST still reject paths containing parent traversal.

#### Scenario: Reject parent traversal
- **WHEN** a client requests a path containing `..`
- **THEN** the system rejects the request without listing entries

#### Scenario: Reject a mounted-NAS symbolic-link escape
- **WHEN** a directory inside the mounted-NAS root is a symbolic link to a location outside that root
- **THEN** the system rejects the request without listing entries

### Requirement: Support only filesystem-backed browsing
The system SHALL provide directory browsing for active local and mounted-NAS storage locations. Non-mounted SMB, NFS, WebDAV, HTTP, HTTPS, external, deleted, or missing storage locations MUST return a distinct unsupported or unavailable response.

#### Scenario: Request an unsupported protocol
- **WHEN** a client requests directory entries for an active storage location whose protocol is not local or mounted
- **THEN** the system returns an unsupported-storage response

#### Scenario: Request a deleted storage location
- **WHEN** a client requests directory entries for a deleted storage location
- **THEN** the system returns a storage-unavailable response
