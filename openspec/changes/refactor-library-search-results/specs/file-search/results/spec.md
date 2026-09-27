## Purpose

Provides a clean, responsive, and robust presentation layer for library search results including flexible sorting controls and an interactive side-by-side details panel.

## ADDED Requirements

### Requirement: Removal of Redundant Tab Selectors
The search results page SHALL NOT display the file category tab selector since file category selection is handled during advanced filtering.

#### Scenario: Verify tabs are absent
- **WHEN** the search results page renders
- **THEN** no category tab selectors (e.g., 全部, 文档, 图片, 视频) are visible

### Requirement: Simplified Sorting Modes
The search results sorting system SHALL support exactly three sorting options: "Relevance" (相关度), "File Size" (文件大小), and "Date" (按日期排序).

#### Scenario: Verify sorting options
- **WHEN** the user opens the sort dropdown
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
