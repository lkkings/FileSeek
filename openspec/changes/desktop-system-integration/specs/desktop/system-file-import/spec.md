## Purpose

Let users add files to FileSeek directly from supported system file managers and choose the destination folder without first opening the app.

## ADDED Requirements

### Requirement: Supported file managers expose a first-level import action
The system SHALL provide an "Add to FileSeek" action as a first-level context-menu item in Windows Explorer, macOS Finder, GNOME Files/Nautilus, and KDE Dolphin when file-manager integration is enabled.

#### Scenario: Use the first-level context action
- **WHEN** the user right-clicks a supported file in a supported file manager
- **AND** file-manager integration is enabled
- **THEN** the first-level context menu contains "Add to FileSeek"

#### Scenario: Unsupported file manager
- **WHEN** the user uses a file manager outside the supported set
- **THEN** FileSeek does not claim that a first-level context action is available

### Requirement: Selected files wake a single FileSeek instance
Invoking the context action SHALL forward the selected file paths to one FileSeek desktop instance. If FileSeek is already running, invoking the action SHALL focus the existing instance instead of creating another desktop process.

#### Scenario: Import while FileSeek is resident
- **WHEN** the user chooses "Add to FileSeek" while FileSeek is hidden in the tray
- **THEN** the existing FileSeek instance receives the selected file paths
- **AND** the main window is shown and focused
- **AND** no second FileSeek desktop process remains running

#### Scenario: Multiple files are selected
- **WHEN** the user invokes the context action with multiple selected files
- **THEN** all selected file paths are presented in FileSeek

### Requirement: System import requires a destination folder
After receiving files from the file manager, FileSeek SHALL show the received file list and the available library folders, and SHALL require the user to choose a destination folder before starting the import.

#### Scenario: Choose a destination folder
- **WHEN** the user confirms a destination folder for received files
- **THEN** FileSeek starts one batch import into that folder
- **AND** import progress and per-file failures are visible

#### Scenario: Cancel the system import
- **WHEN** the user cancels folder selection
- **THEN** no import is started
- **AND** the selected paths are discarded

### Requirement: Invalid or unavailable files are rejected clearly
FileSeek SHALL reject paths that do not exist, are directories, are unreadable, or cannot be mapped to an active storage source. Rejection SHALL be visible to the user and SHALL not silently create an import task.

#### Scenario: A selected file no longer exists
- **WHEN** a received path does not exist
- **THEN** FileSeek reports that path as invalid
- **AND** no import task is created for it

#### Scenario: No active local storage source exists
- **WHEN** received files cannot be mapped to an active storage source
- **THEN** FileSeek explains that an active storage source is required
