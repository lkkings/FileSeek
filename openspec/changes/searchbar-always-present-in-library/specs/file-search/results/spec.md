## Purpose

Provides unified, robust, and interactive presentation interfaces for library file lists, folders, search results, and sorting filters.

## MODIFIED Requirements

### Requirement: Simplified Sorting Modes
The search results sorting system SHALL support exactly three sorting options: "Relevance" (相关度), "File Size" (文件大小), and "Date" (按日期排序).

#### Scenario: Verify sorting options
- **WHEN** the user opens the sort dropdown in SearchResultsView
- **THEN** only "相关度", "文件大小", and "按日期排序" are shown as sort options

### Requirement: Toggleable Sorting Direction
The search results sorting system SHALL provide a direction toggle button that supports ascending (正序) and descending (逆序) ordering.

#### Scenario: Verify ascending and descending sort order
- **WHEN** the user clicks the sorting direction toggle button
- **THEN** the search results order is updated to sort the current mode in the opposite direction and the indicator arrow direction is flipped

### Requirement: Sidebar Detailed Viewer with Flex Layout
The search results page SHALL support a side-by-side split details panel that shows extensive metadata and a high-fidelity preview of the selected search result. On item row selection, the sidebar expands. When expanded, the list rows SHALL dynamically scale their columns via a fluid flex layout to remain legible.

#### Scenario: Open detailed sidebar on item selection
- **WHEN** the user selects a search result item
- **THEN** the detailed sidebar is expanded, showing file tags, paths, dates, descriptions, previews, and quick actions
- **AND** the search result list adjusts dynamically to the remaining screen space without clipping columns

### Requirement: Navigation Back Arrow and Folder ID Sync
The system SHALL support context-aware back navigation. Clicking "返回" in SearchResultsView SHALL return the user to the view from which the search was initiated.
- If the search was initiated from the root Library folder list, the `folder_id` query parameter MUST be empty/null, and the back button SHALL return the user to the root Library folders view.
- If the search was initiated from a specific folder's details view, the `folder_id` query parameter MUST be that folder's ID, and the back button SHALL return the user to that specific folder's details view.

#### Scenario: Search from Library list view
- **WHEN** the user initiates search from the Library list view
- **THEN** the folder_id parameter is sent as null
- **AND** clicking "返回" returns the user to the Library list view

#### Scenario: Search from Folder details view
- **WHEN** the user initiates search from a Folder details view
- **THEN** the folder_id parameter is sent as the active folder's ID
- **AND** clicking "返回" returns the user to that Folder details view

### Requirement: Toggleable Folder Search Bar
The folder details page SHALL hide the search bar by default, exposing a toggle search icon in the breadcrumb header. Clicking the search icon toggles the search bar display.

#### Scenario: Toggle search bar inside folder
- **WHEN** the user enters a folder details view
- **THEN** the search bar is hidden by default
- **WHEN** the user clicks the search toggle button in the header
- **THEN** the search bar is displayed
- **WHEN** the user clicks the search toggle button again
- **THEN** the search bar is hidden

### Requirement: Detail Sidebar in Folder Details View
The folder details page SHALL support expanding a side-by-side split details panel identical in features to the search results page's sidebar when a file is clicked.

#### Scenario: Open file detail sidebar in folder details
- **WHEN** the user clicks a file card in FolderDetailsView
- **THEN** the file details sidebar is expanded side-by-side
- **AND** shows the file name, tags, path, modification date, size, and preview

### Requirement: Shared Auto-closing Sorting component
Both the SearchResultsView and the FolderDetailsView SHALL use a unified sorting dropdown component.
- In FolderDetailsView, "Relevance" (相关度) sorting option is hidden, leaving only "File Size" (按大小) and "Date" (按修改时间).
- The dropdown menu SHALL automatically close when clicking outside the component.

#### Scenario: Unify sorting controls with outside click closing
- **WHEN** the sort dropdown is open
- **AND** the user clicks outside the component
- **THEN** the sorting dropdown menu is automatically closed
