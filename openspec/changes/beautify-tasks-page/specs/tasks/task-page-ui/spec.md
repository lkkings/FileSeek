## Purpose

Defines the user-facing presentation and interaction behavior for the desktop Tasks page so users can monitor file processing work and recover failed tasks efficiently.

## ADDED Requirements

### Requirement: Task queue overview

The Tasks page SHALL present a localized page title and a status summary that distinguishes total tasks, processing tasks, and failed tasks.

#### Scenario: Viewing the overview

- **WHEN** the Tasks page is opened
- **THEN** the page shows the Tasks title and the total, processing, and failed task counts

### Requirement: Task row clarity

Each task row SHALL communicate the file identity, task status, progress, current stage, and error message without changing the task data displayed today.

#### Scenario: Scanning a failed task

- **WHEN** a failed task is rendered
- **THEN** the row shows the file name, status, progress, current stage, and error message with distinct visual emphasis

#### Scenario: Scanning a processing task

- **WHEN** a processing task is rendered
- **THEN** the row shows the current progress and stage using the processing visual state

### Requirement: Task filtering and recovery

The Tasks page SHALL provide status filters for all supported task states and a retry action for failed tasks, while preventing retry when no failed tasks are available.

#### Scenario: Filtering by status

- **WHEN** a user selects a status filter
- **THEN** the selected filter is clearly active and the task list and pagination update to that filter

#### Scenario: Retrying all failed tasks

- **WHEN** no failed tasks are visible
- **THEN** the retry-all action is disabled

### Requirement: Task page state feedback

The Tasks page SHALL provide distinct loading, empty, and error states that do not expose implementation details to the user.

#### Scenario: Loading tasks

- **WHEN** tasks are loading
- **THEN** the page shows a non-blocking loading state that preserves the page layout

#### Scenario: Showing no matching tasks

- **WHEN** the filtered task list is empty
- **THEN** the page shows a localized empty state with guidance to change filters or create tasks

#### Scenario: Showing a task error

- **WHEN** loading tasks fails
- **THEN** the page shows the user-facing error in a visually distinct error state

### Requirement: Accessible and responsive task UI

The Tasks page SHALL preserve keyboard access, semantic labels, localized text, and usable layouts across the existing desktop, compact, and mobile breakpoints.

#### Scenario: Using keyboard navigation

- **WHEN** a user moves keyboard focus through filters, task rows, and actions
- **THEN** each interactive element receives a visible focus state

#### Scenario: Using a narrow layout

- **WHEN** the page width is reduced to the compact or mobile breakpoint
- **THEN** task information and controls remain usable without horizontal scrolling
