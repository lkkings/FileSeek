## Purpose

Reads indexed files from their bound storage locations so previews, thumbnails, and processing use the original source rather than a copied library file.

## ADDED Requirements

### Requirement: Resolve a file through its bound storage
The system SHALL resolve an indexed file's original source path using the storage location bound to that file.

#### Scenario: Preview a local file
- **WHEN** a client previews an indexed local file whose source remains readable
- **THEN** the system streams the original local file

#### Scenario: Preview a NAS file
- **WHEN** a client previews an indexed NAS file whose storage location is active and source remains readable
- **THEN** the system streams the original file through that NAS location

### Requirement: Preserve range requests
The system SHALL support HTTP range requests for source files that support ranged reads.

#### Scenario: Request a byte range
- **WHEN** a client previews a source file with a Range header
- **THEN** the system returns the requested byte range from the original source

### Requirement: Report unavailable sources without deleting indexes
The system SHALL return a distinct unavailable-source response for indexed files whose source or storage location cannot be accessed, and SHALL retain the index.

#### Scenario: Preview an unavailable file
- **WHEN** a client previews an indexed file marked unavailable
- **THEN** the system returns an unavailable-source response and retains the file index

#### Scenario: Source becomes unavailable during access
- **WHEN** an indexed source cannot be opened while it is being read
- **THEN** the system marks the file unavailable, returns an access failure, and retains the file index

### Requirement: Generate thumbnails from source files
The system SHALL generate image and video thumbnails by reading the indexed file through its bound storage location.

#### Scenario: Generate a thumbnail
- **WHEN** a client requests a thumbnail for an available image or video index
- **THEN** the system reads the original source through its bound storage location and returns a generated thumbnail

### Requirement: Process tasks from source files
The system SHALL process document, image, and video tasks using data read from the indexed file's bound storage location.

#### Scenario: Process an indexed file
- **WHEN** a processing task runs for an available indexed file
- **THEN** the task reads the original source through the file's bound storage location and does not create a permanent library copy
