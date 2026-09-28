## Purpose

Define the folder details page layout contract for navigation, tag filtering, pagination, and list-view column alignment.

## ADDED Requirements

### Requirement: Folder details back button

The folder details page SHALL use a visually explicit back button beside the library breadcrumb, not a dropdown-style control.

#### Scenario: Back button is rendered

- **WHEN** the folder details page is displayed
- **THEN** the system SHALL show a back button beside “资源库” with a clear back affordance

#### Scenario: Back button returns to library

- **WHEN** the user clicks the back button
- **THEN** the system SHALL return to the folder library view

### Requirement: Tag filter row placement

The folder details page SHALL display all tag filters on their own row directly below the file type filter row.

#### Scenario: Tag row is below file types

- **WHEN** the folder details page is rendered
- **THEN** the tag filter row SHALL appear below the file type filter row

#### Scenario: Tags overflow horizontally

- **WHEN** the available tags exceed the visible row width
- **THEN** the system SHALL keep all tags on one line and allow horizontal scrolling without wrapping

#### Scenario: Add-tag icon is absent

- **WHEN** the tag filter row is rendered
- **THEN** the system SHALL NOT show a plus-icon “add tag” trigger

### Requirement: File count summary placement

The folder details page SHALL NOT duplicate the file total above the file list when the pagination component already displays the count.

#### Scenario: Duplicate total is absent

- **WHEN** the folder details list is rendered with pagination
- **THEN** the system SHALL NOT display the “共 * 个文件” summary above the file list

### Requirement: Pagination alignment

The folder details pagination SHALL center the page controls and place the total-page statistic on the right side of the same footer row.

#### Scenario: Pagination controls are centered

- **WHEN** the folder details page has multiple pages
- **THEN** the page-number controls SHALL be horizontally centered

#### Scenario: Total statistic is right-aligned

- **WHEN** the pagination footer is rendered
- **THEN** the total-page statistic SHALL be aligned to the right side of the same row, not below the controls

### Requirement: List view column order and alignment

The folder details list view SHALL display columns in the order “预览、文件名、标签、大小”, with centered column headers.

#### Scenario: Column order is correct

- **WHEN** the list view is rendered
- **THEN** the columns SHALL appear in the order “预览、文件名、标签、大小”

#### Scenario: Column headers are centered

- **WHEN** the list view header row is rendered
- **THEN** all column header labels SHALL be horizontally centered
