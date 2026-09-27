## ADDED Requirements

### Requirement: Default Folder Grid Layout
The library page SHALL display the list of folders (`FolderSection`) by default upon initial loading when no search has been executed.

#### Scenario: Display folders by default on land
- **WHEN** the user navigates to the library page
- **THEN** the folder section is visible, presenting a grid of folders with create, edit, and delete options
- **AND** the search results view is completely hidden

### Requirement: Search Initiation and Results Toggle
The library page SHALL switch from the folder view to the search results view (`SearchResultsView`) only after a search has been completed.

#### Scenario: Switch to results on search completion
- **WHEN** the user enters a query in the search bar and triggers the search
- **AND** the search query is executed
- **THEN** the folder section is hidden
- **AND** the search results view is rendered with the corresponding items

### Requirement: Back to Library Navigation
The search results view SHALL provide a navigation control to return to the default library folder view, resetting any query input and active search filters.

#### Scenario: Return to library folder view
- **WHEN** the user clicks the "返回资源库" (Return to Library) button on the search results view
- **THEN** the page switches back to the default library folder view
- **AND** all active search filters and search queries are reset to their initial empty states
