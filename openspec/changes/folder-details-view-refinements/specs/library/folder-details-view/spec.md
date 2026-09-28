## Purpose

Define the folder details page behavior for search toggling, tag selection, responsive file listing, pagination, and file preview interactions.

## ADDED Requirements

### Requirement: Folder search toggle button

The folder details page SHALL provide a search icon button that controls the visibility of the folder search bar.

#### Scenario: Search bar opens

- **WHEN** the user clicks the search icon button while the search bar is closed
- **THEN** the system SHALL show the folder search bar and mark the button as active using a filled icon

#### Scenario: Search bar closes

- **WHEN** the user clicks the active search icon button
- **THEN** the system SHALL hide the folder search bar and restore the non-active icon state

### Requirement: Tag selection from backend

The folder details page SHALL show file type filters and tag filters in the same row, with an add-tag icon button on the right.

#### Scenario: Tag list opens

- **WHEN** the user clicks the add-tag icon button
- **THEN** the system SHALL fetch the available tags from the backend and show a tag selection panel

#### Scenario: Tag is selected

- **WHEN** the user selects a tag in the tag selection panel
- **THEN** the system SHALL show the selected tag in the filter row and filter folder files by that tag

#### Scenario: Tag list fails to load

- **WHEN** the backend tag list request fails
- **THEN** the system SHALL show a retry option and preserve the current folder file list

### Requirement: Summary and sorting alignment

The folder details page SHALL place the file count summary and sorting control in one row, with the sorting control aligned to the right.

#### Scenario: Row layout

- **WHEN** the folder details page is rendered
- **THEN** the file count summary and sorting control SHALL be horizontally aligned in the same row

### Requirement: Responsive file list columns

The list view SHALL display only the preview, tags, file name, and size columns. The system SHALL adapt the visible number of columns and layout when the sidebar expands or collapses.

#### Scenario: Sidebar collapsed on a small screen

- **WHEN** the sidebar is collapsed and the viewport is small
- **THEN** the list view SHALL present the file entries in a floating two-column layout

#### Scenario: Sidebar expanded on a small screen

- **WHEN** the sidebar is expanded and the viewport is small
- **THEN** the list view SHALL present the file entries in a single-column floating layout

#### Scenario: Legacy columns are absent

- **WHEN** the list view is rendered
- **THEN** the system SHALL NOT display the path or action columns

### Requirement: Shared pagination

The folder details page SHALL use the existing shared pagination component for file paging.

#### Scenario: Pagination is rendered

- **WHEN** the folder contains more files than the current page size
- **THEN** the system SHALL render the shared pagination component with the current page and total file count

#### Scenario: Pagination changes page

- **WHEN** the user selects another page
- **THEN** the system SHALL request that page from the backend and update the displayed files

### Requirement: File detail and preview interaction

The system SHALL open the right-side file detail drawer when a file entry is clicked once, and open the file preview when the same file entry is clicked twice in quick succession.

#### Scenario: Single click opens detail drawer

- **WHEN** the user clicks a file entry once
- **THEN** the system SHALL open the right-side file detail drawer for that file

#### Scenario: Double click opens preview

- **WHEN** the user double-clicks a file entry
- **THEN** the system SHALL open the file preview directly
