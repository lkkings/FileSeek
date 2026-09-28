## Purpose

Manages the storage locations that identify where indexed files originate and how their original paths are resolved.

## ADDED Requirements

### Requirement: List storage locations
The system SHALL expose active storage locations, including the built-in local location and all configured NAS locations.

#### Scenario: List locations
- **WHEN** a client requests the storage location list
- **THEN** the system returns the built-in local location and every active NAS location with a stable identifier, display name, type, protocol, endpoint, and account name

#### Scenario: Credentials are redacted
- **WHEN** storage locations are returned
- **THEN** the response does not expose stored passwords or other secrets

### Requirement: Create a NAS storage location
The system SHALL allow a settings client to create a NAS storage location with a stable identifier, display name, protocol, endpoint, and optional account credentials.

#### Scenario: Create NAS location
- **WHEN** a client submits a valid NAS location
- **THEN** the system stores the location and returns its public configuration without secrets

#### Scenario: Reject duplicate identifiers
- **WHEN** a client submits a NAS identifier already used by another storage location
- **THEN** the system rejects the request and leaves existing locations unchanged

### Requirement: Built-in local location is protected
The system SHALL provide a built-in local storage location and SHALL NOT allow it to be deleted.

#### Scenario: Delete local location
- **WHEN** a client attempts to delete the built-in local location
- **THEN** the system rejects the request and the local location remains active

### Requirement: Soft-delete a NAS location
The system SHALL soft-delete a NAS storage location instead of removing its configuration or indexed-file references.

#### Scenario: Delete NAS location
- **WHEN** a client deletes an active NAS location
- **THEN** the system marks the location as deleted, omits it from active location lists, and marks indexed files bound to that location as unavailable

#### Scenario: Indexed files remain after deletion
- **WHEN** a NAS location has bound indexed files and is deleted
- **THEN** the system retains the indexed file records and their storage bindings

### Requirement: Test a storage location connection
The system SHALL allow a client to test whether an active storage location is reachable.

#### Scenario: Connection succeeds
- **WHEN** a client tests a reachable active storage location
- **THEN** the system reports that the connection succeeded

#### Scenario: Connection fails
- **WHEN** a client tests an unreachable active storage location
- **THEN** the system reports a connection failure without exposing stored credentials
