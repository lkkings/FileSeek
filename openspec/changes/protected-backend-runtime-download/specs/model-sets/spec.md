## Purpose

Manages model files as content-defined sets so unchanged models are reused offline while any pinned file change requires a fresh, verified download before use.

## ADDED Requirements

### Requirement: Content-defined model identity
The system SHALL derive a model set identity from the canonical list of model file paths, sizes, and SHA-256 digests. The stable model name SHALL NOT by itself determine the installed directory. Two manifests with the same identity SHALL refer to exactly the same expected files.

#### Scenario: Only tokenizer hash changes
- **WHEN** a new app version changes a tokenizer file digest while the ONNX digest remains unchanged
- **THEN** the app uses a new model set identity and does not report the existing model set as satisfying the new manifest

### Requirement: Verified model set installation
The system SHALL download every file in a model set and verify its size and SHA-256 digest before the set can be selected. Before the first model transfer, the system SHALL measure the listed model sources with a small range request and try the fastest responsive source first. Partial downloads SHALL resume safely, and any file that does not match its pinned digest SHALL be replaced from a listed source rather than accepted.

#### Scenario: Model file is corrupt
- **WHEN** a model set file no longer matches its pinned digest and repair is requested
- **THEN** only files failing verification are downloaded again

#### Scenario: A model mirror is faster
- **WHEN** a model mirror has higher measured throughput than the official model host
- **THEN** model files try that mirror first while retaining the official host as a fallback

#### Scenario: Model download is interrupted
- **WHEN** the model set download is interrupted and retried
- **THEN** completed files are retained and the interrupted file resumes without marking the set complete

### Requirement: Model set selection and switching
The system SHALL select a model set only after all files are present and verified. Switching to a new set SHALL be atomic after successful installation, and the previous complete set SHALL remain available until the new set is ready and cleanup is safe.

#### Scenario: New model set download succeeds
- **WHEN** every file in the new model set is downloaded and verified
- **THEN** the app atomically selects the new set and starts the backend with its directory

#### Scenario: New model set download fails
- **WHEN** the new model set cannot be downloaded or verified
- **THEN** the previous complete model set remains unchanged and the new set is not selected

### Requirement: Offline reuse
When the selected model set is complete and its recorded files are present with their expected sizes, the system SHALL start offline without checking model sources. Full content digest verification during every startup SHALL NOT be required unless repair or model set change handling needs it.

#### Scenario: Subsequent launch offline
- **WHEN** a previously verified model set is selected and the computer has no network connection
- **THEN** initialization starts the backend without accessing any model source

### Requirement: Model set cleanup
After a new model set is complete and selected, the system MAY remove older model sets that are not needed for rollback. The system SHALL NOT remove a model set while it is the selected set or the only complete set.

#### Scenario: Older model sets exist
- **WHEN** a new model set is complete and selected
- **THEN** cleanup removes only model sets older than the retained rollback set
