## Purpose

Registers indexed files from their original storage locations without copying, moving, or otherwise modifying the source files.

## ADDED Requirements

### Requirement: Register a file index from a source location
The system SHALL register a file index using a storage location identifier and the file's original source path.

#### Scenario: Register a local file
- **WHEN** a client registers a readable local file with the local storage location
- **THEN** the system creates an index record bound to the local location and the original source path without writing the file into the library root

#### Scenario: Register a NAS file
- **WHEN** a client registers a readable file with an active NAS storage location
- **THEN** the system creates an index record bound to that NAS location and the original source path without copying the file

#### Scenario: Default storage location
- **WHEN** a client registers a file without supplying a storage location identifier
- **THEN** the system binds the index to the built-in local storage location

### Requirement: Validate the source during registration
The system SHALL verify that the source storage location is active and that the source file is readable before creating an index.

#### Scenario: Deleted storage location
- **WHEN** a client registers a file using a deleted storage location
- **THEN** the system rejects the registration

#### Scenario: Missing source file
- **WHEN** a client registers a source path that cannot be read
- **THEN** the system rejects the registration and does not create a file index

### Requirement: Prevent duplicate content indexes
The system SHALL use the source file content identity as the file index identifier and SHALL NOT create a second index record for content that is already indexed.

#### Scenario: Register identical content
- **WHEN** a client registers file content whose identity matches an existing index
- **THEN** the system reports a duplicate-file error and does not create another index record

### Requirement: Track source availability
The system SHALL retain indexed-file records when their source becomes unavailable and SHALL mark those records as unavailable.

#### Scenario: Source file is removed
- **WHEN** an indexed file's original source can no longer be read
- **THEN** the system marks the index as unavailable while retaining the index record and its source binding

#### Scenario: Source storage is deleted
- **WHEN** the storage location bound to an indexed file is soft-deleted
- **THEN** the system marks the indexed file as unavailable
