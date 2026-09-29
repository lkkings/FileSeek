## Purpose

Defines the desktop Recycle page's recovery-focused presentation, state handling, and preview-free interaction behavior.

## ADDED Requirements

### Requirement: Dedicated recycle page presentation

The Recycle page SHALL present a dedicated page identity with a title, explanatory subtitle, item summary, and content area. Loading, error, empty, populated, and pagination states MUST be visually distinct and remain readable without borrowing search-results-only semantics.

#### Scenario: Page with recoverable items

- **WHEN** recycle-bin data is loaded and contains one or more items
- **THEN** the page shows its dedicated title, item summary, and a list of recoverable items
- **AND** pagination is available when the total exceeds one page

#### Scenario: Empty recycle bin

- **WHEN** recycle-bin data is loaded and contains no items
- **THEN** the page shows a dedicated empty state instead of search-result empty-state wording

#### Scenario: Loading or request failure

- **WHEN** the recycle-bin request is in progress or returns an error
- **THEN** the page shows a distinct loading or error state without rendering list rows

### Requirement: No preview entry points

The Recycle page MUST NOT expose file preview, file detail, or viewer entry points. Item rows MUST NOT render preview controls, and selecting an item MUST NOT open a detail drawer or viewer.

#### Scenario: Item selected for batch action

- **WHEN** the user taps or clicks a recycle item
- **THEN** the item selection state changes without opening a detail drawer or file viewer
- **AND** no preview control is rendered on the row

### Requirement: Recovery operations remain available

The Recycle page SHALL continue to support multi-select, select all, invert selection, restore, and confirmed permanent deletion for selected recycle items. Operation success and failure MUST be reported through the existing notice mechanism.

#### Scenario: Restore selected items

- **WHEN** the user selects items and invokes restore
- **THEN** the selected items are submitted for restoration and the result is reported

#### Scenario: Permanently delete selected items

- **WHEN** the user selects items and invokes permanent deletion
- **THEN** the user must confirm before deletion proceeds
- **AND** the result is reported after the operation completes

### Requirement: Responsive and accessible recycle layout

The Recycle page layout SHALL remain usable from narrow desktop widths through small viewport widths. Recycle rows, summary information, pagination, and batch-action controls MUST preserve readable text, touch targets, and visible keyboard focus.

#### Scenario: Narrow viewport

- **WHEN** the page is displayed at a narrow viewport width
- **THEN** row metadata wraps or reflows without clipping the item name or primary actions
- **AND** interactive controls retain visible focus and adequate target size
