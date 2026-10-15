## Purpose

Lets a resource-library folder observe multiple directories across supported storage sources and automatically import newly created files into that folder and the processing task queue.

## ADDED Requirements

### Requirement: Folder source bindings
The system SHALL allow each library folder to have multiple active source bindings, where each binding identifies one storage source directory. A binding MUST specify the storage source, source directory path, whether descendants are included, and whether watching is enabled.

#### Scenario: Bind multiple directories
- **WHEN** a user binds two different source directories from two active storage sources to one library folder
- **THEN** both bindings are persisted for that folder and appear in the folder's binding list

#### Scenario: Reuse the same source directory for one folder
- **WHEN** a user attempts to save two active bindings for the same storage source and normalized source directory on the same library folder
- **THEN** the system rejects the duplicate binding

### Requirement: Binding validation and overlap prevention
The system MUST only accept bindings whose storage source is active, whose directory can be resolved, and whose storage type supports watching. The system MUST reject an active binding whose watched file set overlaps another active binding assigned to a different library folder.

#### Scenario: Unsupported storage source
- **WHEN** a user attempts to bind an external HTTP storage source
- **THEN** the binding is rejected with an error identifying that watching is unsupported for that storage type

#### Scenario: Conflicting active bindings
- **WHEN** an active binding for a source directory or ancestor directory is already assigned to a different library folder
- **THEN** creating the new overlapping active binding fails without changing either folder's assignments

#### Scenario: Binding to an unavailable directory
- **WHEN** a user attempts to bind a directory that cannot be read
- **THEN** the binding is rejected with a validation error

### Requirement: Automatically import new files
While the backend is running and a binding is enabled, the system SHALL detect a file newly created under the watched directory and register it in the bound library folder. Successful registration MUST create a processing task in the queued state. When a binding is first enabled, the system SHALL scan its watched directory and import existing recognizable supported files through the same registration flow.

#### Scenario: Existing file is present when a binding is enabled
- **WHEN** a supported file already exists under a newly enabled binding's watched directory
- **THEN** the file is registered in the bound library folder
- **AND** a queued processing task is created for that file

#### Scenario: New file appears in a watched directory
- **WHEN** a supported file is created in a bound directory while its binding is enabled and the backend is running
- **THEN** the file is registered in the bound library folder
- **AND** a queued processing task is created for that file

#### Scenario: New file appears in a descendant directory
- **WHEN** a supported file is created in a descendant directory and the binding includes descendants
- **THEN** the file is registered in the bound library folder
- **AND** a queued processing task is created for that file

#### Scenario: Filesystem event is missed
- **WHEN** a supported file is created while the backend is running but the storage source does not deliver a filesystem event
- **THEN** a periodic binding scan detects the file
- **AND** a queued processing task is created for it

#### Scenario: Unsupported file appears in a watched directory
- **WHEN** an unsupported file is created in a watched directory
- **THEN** no file record or processing task is created
- **AND** the binding health records a recent import rejection for that file

### Requirement: Stable-file import
The system MUST NOT register a newly detected file until it is present and its size and modification time are unchanged across the configured number of consecutive settling intervals. A file that is still changing MUST remain pending for a later stability check instead of being marked missing or imported. If a file disappears before it is stable, the system MUST abandon that import attempt.

#### Scenario: File is still being copied
- **WHEN** a watched file is created and its size changes during the settling interval
- **THEN** the system waits before attempting registration

#### Scenario: Writer pauses during the first stable interval
- **WHEN** a watched file has unchanged size and modification time for one settling interval but changes during a subsequent stability check
- **THEN** the system does not register the file
- **AND** the system schedules another stability check

#### Scenario: Temporary file is removed
- **WHEN** a detected file no longer exists before import processing starts
- **THEN** no file record or processing task is created for it

### Requirement: Import deduplication
The system MUST attempt each watched source path only once per import run and MUST NOT create a second file record for a file that already exists in the library. Duplicate detections MUST not create additional processing tasks.

#### Scenario: Watch event is repeated
- **WHEN** the watcher emits duplicate events for one already imported source path
- **THEN** no duplicate file record or task is created

#### Scenario: Watched file is already in the library
- **WHEN** a detected source path already has a library file record
- **THEN** the watcher does not create another task
- **AND** the file remains associated with its existing library folder

### Requirement: Watcher lifecycle
The system SHALL restore enabled bindings when the backend starts and MUST stop observing bindings when they are disabled, deleted, or their folder or storage source becomes unavailable or is deleted. Stopping or restarting watcher sessions MUST NOT delete files that have already been imported.

#### Scenario: Backend restarts with active bindings
- **WHEN** the backend starts while enabled bindings are persisted
- **THEN** the backend starts watching those bindings

#### Scenario: Binding is disabled
- **WHEN** a user disables an enabled folder source binding
- **THEN** the system stops watching its directory
- **AND** existing library files and tasks are retained

#### Scenario: Folder or storage source is deleted
- **WHEN** a bound library folder or storage source is deleted
- **THEN** its related bindings no longer observe files

### Requirement: Binding health visibility
The system SHALL expose binding status and recent watcher or import errors. Binding responses MUST distinguish active watching from disabled, unsupported, or unavailable states without exposing storage credentials.

#### Scenario: Binding encounters an import failure
- **WHEN** a watched file import fails
- **THEN** the binding's health information identifies the source path and a user-readable error message
- **AND** the error is available through the binding API

#### Scenario: Binding becomes unavailable
- **WHEN** a watched directory becomes unavailable while the backend is running
- **THEN** the binding's health information marks the watcher as unavailable
