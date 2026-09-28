## Purpose

Define the folder details page contract for selecting files, performing confirmed batch operations, and keeping view and tag controls usable.

## ADDED Requirements

### Requirement: Batch selection across view modes
The folder details page SHALL provide the same batch selection behavior in grid view and list view.

#### Scenario: List view activates batch mode
- **WHEN** the user long-presses or otherwise activates selection on a file row in list view
- **THEN** the file row SHALL become selected and the batch operation bar SHALL appear

#### Scenario: Selection persists across view switches
- **WHEN** files are selected in one view mode and the user switches between grid and list views
- **THEN** the same files SHALL remain selected

### Requirement: Confirmed batch recycle operation
The folder details page SHALL let users move all selected files to the recycle bin after confirmation.

#### Scenario: Recycle confirmation is required
- **WHEN** the user chooses the batch move-to-recycle action with one or more files selected
- **THEN** the system SHALL show a confirmation dialog and SHALL NOT call the recycle operation before confirmation

#### Scenario: Recycle operation succeeds
- **WHEN** the user confirms moving the selected files to the recycle bin and the operation succeeds
- **THEN** the system SHALL move the selected files to the recycle bin, clear the selection, refresh the folder contents, and show a success message containing the number of files

#### Scenario: Recycle operation fails
- **WHEN** the user confirms the operation and it fails
- **THEN** the system SHALL keep the dialog available, retain the selection, and show a failure message

### Requirement: Confirmed batch move operation
The folder details page SHALL let users move all selected files to another existing folder after confirmation.

#### Scenario: Move target selection
- **WHEN** the user chooses the batch move-to-folder action with one or more files selected
- **THEN** the system SHALL show a confirmation dialog that allows the user to select one destination folder and SHALL exclude the current folder

#### Scenario: Move confirmation is required
- **WHEN** the user invokes the batch move action
- **THEN** the system SHALL NOT move files until a destination is selected and the user confirms

#### Scenario: Move operation succeeds
- **WHEN** the user confirms moving the selected files to a valid destination and the operation succeeds
- **THEN** the system SHALL update the files' folder, clear the selection, refresh the folder contents, and show a success message containing the number of files

#### Scenario: Move operation fails
- **WHEN** the user confirms a valid destination and the move operation fails
- **THEN** the system SHALL retain the selection and show a failure message

### Requirement: View switch placement
The folder details page SHALL place the view switch icons at the far left of the sort controls.

#### Scenario: View switch is left of sort controls
- **WHEN** the folder details control row is rendered
- **THEN** the grid/list view switch SHALL appear immediately to the left of the sort control and no view switch SHALL remain in the page header

### Requirement: Default tags on load failure
The folder details page SHALL use the default tag set when the tag-list request fails.

#### Scenario: Default tags are available
- **WHEN** the tag-list request fails
- **THEN** the tag filter row SHALL offer “全部”, “文档”, “图片”, and “视频” and remain clickable

#### Scenario: Tag filter continues to query files
- **WHEN** the user selects a default tag while the tag-list request has failed
- **THEN** the folder contents query SHALL use that tag as its filter value
