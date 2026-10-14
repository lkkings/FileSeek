## Purpose

Provides a deterministic, verified, and reusable Python runtime for the desktop backend without bundling hundreds of megabytes of dependencies in every app update.

## ADDED Requirements

### Requirement: Build-time runtime source list
The system SHALL generate a per-platform runtime source list containing the exact Python interpreter archive and every production dependency wheel selected by the backend lock file. The list SHALL include each file's size and SHA-256 digest and SHALL be embedded in the app so it cannot be replaced after the app is signed. A build SHALL fail if the committed source list is stale, does not match the lock-derived runtime identity, or cannot be parsed by the app.

#### Scenario: Lock file changes
- **WHEN** the backend lock file changes and the source lists are not regenerated
- **THEN** the build or source-list check fails instead of producing an app with an inconsistent runtime identity

#### Scenario: Unsupported platform
- **WHEN** the app runs on a platform with no embedded source list
- **THEN** initialization reports that the platform is unsupported and does not attempt runtime installation

### Requirement: Verified runtime download
The system SHALL download the interpreter and wheel files only from their listed official source or mirrors. Each file SHALL be checked against its pinned size and SHA-256 digest before it is used. A mirror that supplies a different file SHALL be treated as a failed source, not as an installation candidate.

#### Scenario: Mirror returns a wrong file
- **WHEN** a mirror responds successfully with bytes whose digest differs from the pinned digest
- **THEN** the system rejects that response and tries the next source or retry policy

#### Scenario: Interrupted download
- **WHEN** a runtime download is interrupted and the user retries
- **THEN** previously completed files are retained and the interrupted partial file resumes from the bytes already on disk

### Requirement: Atomic runtime installation
The system SHALL install a runtime in a staging directory, verify the interpreter and required wheel files, and move the completed directory to its final runtime identity only after verification. A failed or interrupted installation SHALL leave no runtime marked complete and SHALL be safe to retry.

#### Scenario: Installation is interrupted
- **WHEN** the app exits or is cancelled while installing a runtime
- **THEN** no incomplete directory is reported as installed and the next attempt can resume or rebuild it

#### Scenario: Wheel installation fails
- **WHEN** dependency installation returns a non-zero status after all files have passed their digest checks
- **THEN** initialization fails at the installation step and does not switch to the new runtime

### Requirement: Runtime reuse and replacement
The system SHALL identify a runtime by the normalized backend lock file, Python version, and interpreter release. The system SHALL reuse an already installed runtime with the same identity without network access. When the identity changes, the system SHALL download and install the new runtime, keep the previous runtime available for rollback, and remove runtimes older than the previous one only after the new runtime is complete.

#### Scenario: Code-only app update
- **WHEN** a new app version changes protected backend code but the runtime identity is unchanged
- **THEN** the new version starts immediately with the already installed runtime and does not download the interpreter or wheels again

#### Scenario: Dependency update
- **WHEN** a new app version has a different runtime identity
- **THEN** initialization downloads the new runtime before starting the backend and retains the prior runtime for rollback

### Requirement: Runtime repair
The system SHALL provide a repair action that discards the incomplete or damaged runtime matching the current identity and downloads its files again. The repair action SHALL NOT delete the previous complete runtime while repairing the current one.

#### Scenario: Current runtime is damaged
- **WHEN** the current runtime is incomplete or its required interpreter is missing and the user chooses repair
- **THEN** the system rebuilds the current runtime while leaving the previous runtime untouched
