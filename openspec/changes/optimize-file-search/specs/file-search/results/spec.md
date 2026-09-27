## MODIFIED Requirements

### Requirement: Toggleable Sorting Direction
The search results sorting system SHALL support toggling ascending (正序) and descending (逆序) ordering. Clicking the currently active sorting mode within the sorting dropdown menu SHALL toggle the sorting direction. Additionally, the main sort button and dropdown list SHALL display separate, direction-specific indicator icons for ascending and descending states. No separate direction toggle button SHALL be displayed next to the sorting dropdown.

#### Scenario: Verify ascending and descending sort order toggling on dropdown click
- **WHEN** the user opens the sorting dropdown and clicks on the already active sorting mode
- **THEN** the search results order is updated to sort the current mode in the opposite direction
- **AND** the sort button's main icon updates to display a direction-specific indicator icon (ascending icon for ascending sort, descending icon for descending sort)

### Requirement: Sidebar Detailed Viewer with Flex Layout
The search results page SHALL support a side-by-side split details panel that shows extensive metadata and a high-fidelity preview of the selected search result. On item row selection, the sidebar expands. When expanded, the list rows SHALL dynamically scale their columns via a fluid flex layout to remain legible. The details sidebar SHALL NOT contain any close buttons in its header, and SHALL instead close when clicking on the backdrop overlay area outside the sidebar on small screens (<= 1024px).

#### Scenario: Open detailed sidebar and close via backdrop click
- **WHEN** the user selects a search result item on a small screen (<= 1024px)
- **THEN** the detailed sidebar/drawer is expanded, showing file tags, paths, dates, descriptions, and previews, and a blurred backdrop is displayed behind it
- **AND** when the user clicks on the backdrop area outside the sidebar drawer
- **THEN** the sidebar drawer closes

## ADDED Requirements

### Requirement: Removal of Redundant Row actions
The search results page SHALL NOT display individual row preview (eye) or option menu (more) actions, as these actions are fully handled in the side-by-side split details panel.

#### Scenario: Verify row actions are absent
- **WHEN** the search results page renders
- **THEN** no individual row preview or option menu buttons are visible on any search result row

### Requirement: Small Screen List Preview Removal
On small screens (<= 780px), the search results page SHALL NOT display the inline file preview area within the result list rows to preserve horizontal screen space.

#### Scenario: Verify list previews are hidden on mobile
- **WHEN** the search results page is viewed on a screen size of 780px or smaller
- **THEN** the inline preview area within the search result list rows is hidden
- **AND** the file preview is still accessible within the details drawer when selected
