## Purpose

Define bulk task queue controls that let users terminate incomplete work, restore terminated work, and clean completed task records without pausing the scheduler.

## ADDED Requirements

### Requirement: Remove task status filtering

The desktop Tasks page SHALL NOT provide task-status filtering controls.

#### Scenario: Opening the Tasks page

- **WHEN** the Tasks page is opened
- **THEN** the page lists tasks across all statuses with pagination
- **AND** the page does not expose task-status filter controls

### Requirement: One-click terminate incomplete tasks

The system SHALL provide a one-click terminate action that changes all incomplete tasks from `queued` or `processing` to `cancelled` while the task scheduler remains running and accepting work.

#### Scenario: Terminating incomplete tasks

- **WHEN** the user activates one-click terminate
- **AND** queued and processing tasks exist
- **THEN** every queued and processing task transitions to `cancelled`
- **AND** failed, completed, and already cancelled tasks retain their status
- **AND** the task scheduler remains running and accepting new work

#### Scenario: No incomplete tasks

- **WHEN** no queued or processing tasks exist
- **THEN** the one-click terminate control is disabled

### Requirement: One-click continue cancelled tasks

The system SHALL provide a one-click continue action that changes all cancelled tasks to `queued` while the task scheduler remains running and accepting work.

#### Scenario: Continuing cancelled tasks

- **WHEN** the user activates one-click continue
- **AND** cancelled tasks exist
- **THEN** every cancelled task transitions to `queued`
- **AND** queued, processing, completed, and failed tasks retain their status
- **AND** the task scheduler remains running and accepting new work

#### Scenario: No cancelled tasks

- **WHEN** no cancelled tasks exist
- **THEN** the one-click continue control is disabled

### Requirement: One-click delete completed tasks

The system SHALL provide a one-click delete action that removes all completed task records while preserving indexed files.

#### Scenario: Deleting completed tasks

- **WHEN** the user activates one-click delete completed tasks
- **AND** completed tasks exist
- **THEN** every completed task record is removed
- **AND** files associated with completed tasks remain available in the library

#### Scenario: No completed tasks

- **WHEN** no completed tasks exist
- **THEN** the one-click delete completed control is disabled

### Requirement: Bulk operation consistency

Bulk task operations SHALL operate across all pages and SHALL NOT lose updates to scheduler-owned processing tasks.

#### Scenario: Handling more tasks than one page

- **WHEN** a bulk operation is activated
- **THEN** it applies to every matching task, including tasks outside the currently displayed page

#### Scenario: Continuing during cancellation cleanup

- **WHEN** a processing task is still completing termination cleanup
- **AND** the user activates one-click continue
- **THEN** the system does not transition that task to `queued` until its cancellation is finalized
