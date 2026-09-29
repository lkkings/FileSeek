## Purpose

Keep the FileSeek desktop shell resident in the system tray while preserving the externally managed backend process and giving users an explicit restore-and-quit path.

## ADDED Requirements

### Requirement: Closing the main window keeps FileSeek resident
The desktop application SHALL hide the main window when the user invokes its close action. The application process SHALL remain running, the tray entry SHALL remain available, and the external backend process SHALL not be started or stopped.

#### Scenario: Close the main window
- **WHEN** the user clicks the main window close button
- **THEN** the main window is hidden
- **AND** the FileSeek process remains running
- **AND** the tray entry remains available
- **AND** the external backend process state is unchanged

#### Scenario: Restore from the tray
- **WHEN** the user chooses the tray action to open FileSeek
- **THEN** the existing main window is shown and focused
- **AND** no additional FileSeek desktop process is created

### Requirement: Quitting is explicit
The desktop application SHALL provide an explicit tray action to quit. Quitting SHALL exit the FileSeek desktop process without stopping an externally managed backend process.

#### Scenario: Quit from the tray
- **WHEN** the user chooses Quit from the tray
- **THEN** the FileSeek desktop process exits
- **AND** the external backend process remains running

### Requirement: Silent startup at login
The system SHALL allow the user to enable silent startup. When enabled, user login SHALL start FileSeek without showing the main window, while keeping the tray entry available. When disabled, login SHALL not start FileSeek.

#### Scenario: Login with silent startup enabled
- **WHEN** the user logs in after enabling silent startup
- **THEN** FileSeek starts without showing the main window
- **AND** the tray entry is available
- **AND** no backend process is started by FileSeek

#### Scenario: Login with silent startup disabled
- **WHEN** the user logs in after disabling silent startup
- **THEN** FileSeek does not start automatically

### Requirement: External backend availability is observable
The tray SHALL indicate whether the external backend is reachable. Missing backend connectivity SHALL not silently misrepresent FileSeek as ready.

#### Scenario: Backend is unavailable while resident
- **WHEN** FileSeek is resident and the external backend cannot be reached
- **THEN** the tray presents an unavailable or disconnected state
