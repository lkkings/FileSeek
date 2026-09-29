## Purpose

Give users explicit, truthful control over FileSeek's operating-system integration and startup behavior.

## ADDED Requirements

### Requirement: Settings expose system integration controls
The settings UI SHALL expose separate controls for silent startup and file-manager integration. Both controls SHALL default to off on a fresh installation.

#### Scenario: Fresh installation
- **WHEN** FileSeek is first installed
- **THEN** silent startup is off
- **AND** file-manager integration is off

#### Scenario: Enable silent startup
- **WHEN** the user enables silent startup
- **THEN** the operating system is configured to start FileSeek silently at login
- **AND** the setting reflects the resulting state

#### Scenario: Disable file-manager integration
- **WHEN** the user disables file-manager integration
- **THEN** the supported file-manager context action is removed or disabled
- **AND** the setting reflects the resulting state

### Requirement: Integration status reflects the operating system
The settings UI SHALL display integration status based on the actual operating-system registration or extension state, not only a locally stored preference.

#### Scenario: Operating-system registration is missing
- **WHEN** an enabled integration is no longer present in the operating system
- **THEN** the settings UI shows that integration as off or unavailable

#### Scenario: macOS Finder extension requires system approval
- **WHEN** the Finder Sync extension is bundled but not enabled in macOS system settings
- **THEN** FileSeek shows that the Finder integration is not active
- **AND** provides a path to the relevant macOS system settings
