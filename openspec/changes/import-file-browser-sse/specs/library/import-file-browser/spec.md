## Purpose

Lets users select multiple files from configured storage, start one folder import, and observe registration and processing progress through a resumable event stream where item failures do not stop the batch.

## ADDED Requirements

### Requirement: Start a batch import
The system SHALL accept a non-empty batch of file paths bound to storage locations and a target folder, validate the request, create an import session, and return an import identifier with the total item count.

#### Scenario: Start a valid import
- **WHEN** a client submits a non-empty batch of readable file paths and an existing target folder
- **THEN** the system creates an import session and returns its identifier and total item count

#### Scenario: Reject an invalid request before starting
- **WHEN** a client submits an empty batch or a target folder that does not exist
- **THEN** the system rejects the request and does not create an import session

### Requirement: Stream import progress over SSE
The system SHALL provide an SSE stream for an import session that emits ordered events for batch start, item start, item registration, task progress, item completion, item failure, and batch completion. The stream MUST report both registration progress and background task-processing progress.

#### Scenario: Follow a successful item
- **WHEN** an item is registered and its processing task advances and completes
- **THEN** the stream emits item start, registration, task progress, and item completion events for that item

#### Scenario: Receive the batch summary
- **WHEN** every item in the batch has reached a completed or failed terminal state
- **THEN** the stream emits a batch completion event containing total, succeeded, and failed counts

#### Scenario: Reject an unauthenticated stream
- **WHEN** a client requests an import event stream without valid API authentication
- **THEN** the system rejects the request before opening the event stream

### Requirement: Continue after an item failure
The system MUST process each batch item independently. A duplicate, unreadable, unsupported, or processing failure for one item SHALL emit an item failure event and allow the remaining items to continue.

#### Scenario: Continue after one failed item
- **WHEN** one item fails and later items are valid
- **THEN** the system emits a failure event for the failed item and continues processing the later items

#### Scenario: Complete a batch with every item failed
- **WHEN** every item fails
- **THEN** the system emits a failure event for each item and a batch completion event with zero succeeded items and the total as failed

#### Scenario: Preserve successful items after a later failure
- **WHEN** an earlier item succeeds and a later item fails
- **THEN** the system retains the successful item's index and task result

### Requirement: Resume an import event stream
The system SHALL keep an import session running when its event stream disconnects and support reconnecting with `Last-Event-ID` by replaying events after the supplied identifier.

#### Scenario: Disconnect and reconnect
- **WHEN** the event stream disconnects while the import session continues and the client reconnects with the last received event identifier
- **THEN** the system resumes the stream with events that occurred after that identifier

#### Scenario: Reconnect after completion
- **WHEN** a client reconnects after the batch has completed
- **THEN** the system replays the remaining buffered events and closes the stream after the batch completion event

### Requirement: Browse and select files in the import dialog
The import dialog SHALL let users switch between browsable active storage locations, navigate directories, select files, select all files, and invert the current file selection. File selection MUST persist while the user navigates directories or switches storage tabs.

#### Scenario: Open the import dialog from a folder card
- **WHEN** the user activates the import-file action on a folder card
- **THEN** the dialog opens for that folder and does not expose an import-folder action

#### Scenario: Navigate and retain selections
- **WHEN** the user selects files in one directory and navigates to another directory or storage tab
- **THEN** the previously selected files remain selected for import

#### Scenario: Select all and invert selection
- **WHEN** the user chooses select all and then invert selection
- **THEN** the dialog selects every file in the current directory and then replaces the selection with the files that were not selected

### Requirement: Show import progress in the dialog
The import dialog SHALL show the batch's overall progress and each selected file's current state, including queued, registered, processing, failed, and completed.

#### Scenario: Show a failed item without blocking the batch
- **WHEN** an item fails while other items continue
- **THEN** the dialog marks that item failed with its error and continues updating progress for the remaining items

#### Scenario: Close and reopen progress
- **WHEN** the user closes and reopens the import progress view while the session is still active
- **THEN** the dialog reconnects to the import event stream and shows the current item states
