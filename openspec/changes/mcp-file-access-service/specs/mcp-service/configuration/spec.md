## Purpose

Provides UI in FileSeek Desktop for managing MCP service configuration and viewing/managing file access grants.

## ADDED Requirements

### Requirement: Generate MCP configuration

The Desktop settings page SHALL generate a valid MCP configuration JSON that users can copy into their MCP client.

#### Scenario: Generate configuration with default paths
- **WHEN** user opens MCP settings page
- **THEN** the system displays a JSON configuration with the MCP service executable path resolved from the application bundle

#### Scenario: Copy configuration to clipboard
- **WHEN** user clicks "Copy Configuration" button
- **THEN** the system copies the JSON configuration to clipboard and shows a success toast

### Requirement: Open MCP client config directory

The Desktop settings page SHALL provide shortcuts to open common MCP client configuration directories.

#### Scenario: Open Claude Desktop config directory (macOS)
- **WHEN** user clicks "Open Claude Config Directory"
- **THEN** the system opens `~/Library/Application Support/Claude/` in Finder

#### Scenario: Config location varies by platform
- **WHEN** the system detects the platform
- **THEN** the displayed config paths match the platform conventions (macOS/Windows/Linux)

### Requirement: Display active grants

The MCP settings page SHALL display all currently active file and folder grants with remaining time.

#### Scenario: Show active file grant
- **WHEN** a file has an active grant with 5 minutes remaining
- **THEN** the settings page displays the file name, "File" badge, and "5 minutes remaining"

#### Scenario: Show active folder grant
- **WHEN** a folder has an active grant with 10 minutes remaining
- **THEN** the settings page displays the folder name, "Folder" badge, file count, and "10 minutes remaining"

#### Scenario: No active grants
- **WHEN** there are no active grants
- **THEN** the page displays "No active grants" message

#### Scenario: Real-time countdown
- **WHEN** grants are displayed
- **THEN** the remaining time updates every minute without requiring page refresh

### Requirement: Revoke individual grant

The MCP settings page SHALL allow users to manually revoke individual grants.

#### Scenario: Revoke file grant
- **WHEN** user clicks "Revoke" on a file grant
- **THEN** the system removes the grant from mcp-grants.json and updates the display

#### Scenario: Revoke folder grant
- **WHEN** user clicks "Revoke" on a folder grant
- **THEN** the system removes the grant and all files in that folder lose access

### Requirement: Clear expired grants

The MCP settings page SHALL provide a button to remove all expired grants from storage.

#### Scenario: Clear expired grants
- **WHEN** user clicks "Clear Expired Grants" and expired grants exist
- **THEN** the system removes expired grants from mcp-grants.json and shows count of removed grants

#### Scenario: No expired grants to clear
- **WHEN** user clicks "Clear Expired Grants" and no expired grants exist
- **THEN** the system shows a message indicating all grants are current

### Requirement: Clear all grants

The MCP settings page SHALL provide a button to revoke all active grants.

#### Scenario: Clear all grants with confirmation
- **WHEN** user clicks "Clear All Grants"
- **THEN** the system prompts for confirmation before removing all grants

#### Scenario: User confirms clear all
- **WHEN** user confirms the "Clear All" action
- **THEN** the system empties mcp-grants.json and updates the display

### Requirement: Default authorization duration setting

The MCP settings page SHALL allow users to configure the default grant duration.

#### Scenario: Change default duration
- **WHEN** user sets default duration to 30 minutes
- **THEN** future grant requests suggest 30 minutes as the default duration

#### Scenario: Duration persists across app restarts
- **WHEN** user changes default duration and restarts Desktop
- **THEN** the configured duration is preserved

### Requirement: MCP service status indication

The MCP settings page SHALL display whether the MCP service configuration is ready to use.

#### Scenario: Valid configuration exists
- **WHEN** the MCP service executable is found in the application bundle
- **THEN** the page displays "Ready to configure" status with green indicator

#### Scenario: Service executable missing
- **WHEN** the MCP service executable is not found
- **THEN** the page displays an error indicating the service is unavailable

### Requirement: Help text for setup process

The MCP settings page SHALL provide step-by-step instructions for enabling MCP access.

#### Scenario: Display setup steps
- **WHEN** user views the MCP settings page
- **THEN** the page shows numbered steps: (1) ensure MCP client installed, (2) copy config, (3) restart client, (4) test connection

#### Scenario: Link to MCP documentation
- **WHEN** user clicks "Learn more about MCP"
- **THEN** the system opens external documentation in the default browser
