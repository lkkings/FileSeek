## Purpose

定义搜索结果页的文件列表展示、批量文件管理、文件详情抽屉和分页行为，使搜索后的文件整理流程与文件夹详情页保持一致。

## ADDED Requirements

### Requirement: Search results without category tabs

搜索结果页 SHALL NOT render a category tab bar containing “全部”、“文档”、“图片”或“视频”。文件类型筛选 SHALL remain available through the advanced filter flow rather than the search results page tab bar.

#### Scenario: Category tabs are absent

- **WHEN** the user views completed search results
- **THEN** the page SHALL NOT show the “全部”、“文档”、“图片” and “视频” tab bar
- **AND** the results SHALL display all files returned by the active search filters

### Requirement: Single-column search result rows

搜索结果页 SHALL display each returned file as one row in a single-column list. Each row SHALL show the file preview, file name, time, size, and tags, and SHALL use visual styling consistent with the folder details table row.

#### Scenario: Required row information is displayed

- **WHEN** a search result is displayed
- **THEN** its row SHALL show a preview, file name, time, size, and tags in one single-column result list
- **AND** long file names SHALL remain readable without obscuring the other row information

#### Scenario: Rows use one result column

- **WHEN** the viewport or browser window changes size
- **THEN** result rows SHALL stack vertically as one column rather than forming a multi-column grid

### Requirement: Search result detail drawer

搜索结果页 SHALL open the right-side file detail drawer when the user clicks a file row outside batch selection mode.

#### Scenario: Row click opens detail drawer

- **WHEN** the user clicks an unselected search result row
- **THEN** the right-side file detail drawer SHALL open for that file
- **AND** the drawer SHALL provide the same file details and actions as the folder details page

#### Scenario: Batch mode row click selects

- **WHEN** batch selection mode is active and the user clicks a result row
- **THEN** the row selection SHALL toggle instead of opening the file detail drawer

### Requirement: Long-press batch selection

搜索结果页 SHALL activate batch selection mode when the user long-presses a result row. After activation, the page SHALL show the batch operation bar and allow additional rows to be selected or deselected.

#### Scenario: Long press activates batch mode

- **WHEN** the user long-presses a result row
- **THEN** that row SHALL become selected
- **AND** the batch operation bar SHALL appear
- **AND** the page SHALL indicate that batch selection mode is active

#### Scenario: Batch selection can be changed

- **WHEN** batch selection mode is active and the user clicks or long-presses another result row
- **THEN** that row SHALL be selected if it was unselected, or deselected if it was already selected

#### Scenario: Batch selection can be cleared

- **WHEN** the user cancels batch mode or clears the selection
- **THEN** all result row selections SHALL be cleared and the batch operation bar SHALL disappear

### Requirement: Confirmed batch move to recycle

搜索结果页 SHALL allow users to move all selected search results to the recycle bin after confirmation.

#### Scenario: Recycle confirmation is required

- **WHEN** the user chooses the batch move-to-recycle action with one or more files selected
- **THEN** the system SHALL show a confirmation dialog and SHALL NOT send the recycle request before confirmation

#### Scenario: Recycle operation succeeds

- **WHEN** the user confirms the operation and the service succeeds
- **THEN** the selected files SHALL be moved to the recycle bin, the selection SHALL be cleared, the current search results SHALL be refreshed, and a success message containing the file count SHALL be shown

#### Scenario: Recycle operation fails

- **WHEN** the user confirms the operation and the service fails
- **THEN** the selected files SHALL remain selected, the confirmation flow SHALL remain recoverable, and a failure message SHALL be shown

### Requirement: Confirmed batch move to folder

搜索结果页 SHALL allow users to move all selected search results to an existing destination folder after destination selection and confirmation.

#### Scenario: Move target selection

- **WHEN** the user chooses the batch move-to-folder action with one or more files selected
- **THEN** the system SHALL show a destination folder selection dialog

#### Scenario: Move confirmation is required

- **WHEN** the user invokes the batch move-to-folder action
- **THEN** the system SHALL NOT move files until a valid destination folder is selected and the user confirms

#### Scenario: Move operation succeeds

- **WHEN** the user confirms a valid destination and the service succeeds
- **THEN** the selected files SHALL be moved, the selection SHALL be cleared, the current search results SHALL be refreshed, and a success message containing the file count SHALL be shown

#### Scenario: Move operation fails

- **WHEN** the user confirms a valid destination and the service fails
- **THEN** the selected files SHALL remain selected, the destination dialog SHALL remain recoverable, and a failure message SHALL be shown

### Requirement: Search results pagination

搜索结果页 SHALL use the shared pagination component to display the current page, total item count, and total page count, and to change the search result page.

#### Scenario: Pagination is rendered

- **WHEN** the active search returns more results than the current page size
- **THEN** the shared pagination component SHALL show the current page, total result count, and total page count

#### Scenario: Pagination requests another page

- **WHEN** the user selects another page
- **THEN** the system SHALL request that page using the current search filters, sorting, and page size
- **AND** the displayed results SHALL update to the returned page

#### Scenario: Current page becomes empty after an operation

- **WHEN** a batch operation removes all files on the last non-first page and the search results refresh
- **THEN** the system SHALL request the closest still-existing page instead of leaving the page on an empty out-of-range page
