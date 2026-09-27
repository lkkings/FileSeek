## MODIFIED Requirements

### Requirement: Simplified Sorting Modes
The search results sorting system SHALL support exactly three sorting options: "Relevance" (相关度), "File Size" (文件大小), and "Date" (按日期排序).
The SortMode of SortControls component SHALL be restricted strictly to "relevance", "created_at", and "size".
In the search results page (SearchResultsView), the default sorting mode SHALL be "relevance", and in the folder details view (FolderDetailsView), the default sorting mode SHALL be "created_at".

#### Scenario: Verify sorting options
- **WHEN** the user opens the sort dropdown in SearchResultsView
- **THEN** only "相关度", "文件大小", and "按日期排序" are shown as sort options
- **AND** the active sort mode is "relevance" by default

#### Scenario: Verify folder details sorting default
- **WHEN** the folder details view (FolderDetailsView) loads
- **THEN** the default active sort mode is "created_at"

### Requirement: Shared Auto-closing Sorting component
Both the SearchResultsView and the FolderDetailsView SHALL use a unified sorting dropdown component.
- In FolderDetailsView, "Relevance" (相关度) sorting option is hidden, leaving only "File Size" (按大小) and "Date" (按修改时间).
- The dropdown menu SHALL automatically close when clicking outside the component.
- The component properties or search state MUST enforce that the sorting fields (sort_by and sort_order) are not empty on api requests.

#### Scenario: Unify sorting controls with outside click closing
- **WHEN** the sort dropdown is open
- **AND** the user clicks outside the component
- **THEN** the sorting dropdown menu is automatically closed

## ADDED Requirements

### Requirement: Backend Paged Counter Category Statistic
The search response data (SearchResponseData) SHALL include a `counter` field containing the count of files in each category (document, image, video). The frontend category selection/tabs and overall file count display SHALL consume the `counter` returned from the API rather than calculating counts based on the subset of items on the current page.

#### Scenario: Verify category statistics count
- **WHEN** search results or folder details API response returns the data with a `counter` of `{"image":0,"document":1,"video":10}`
- **THEN** the category counter statistics and totals match the API returned values instead of the length of the currently loaded paged items
