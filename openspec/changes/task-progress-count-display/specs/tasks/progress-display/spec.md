## Purpose

Defines how task progress is represented as a completed-to-total count pair and presented consistently across task monitoring and import surfaces.

## ADDED Requirements

### Requirement: Task progress is count-based
The system SHALL represent processing progress with a completed count and a positive total count, and user-facing progress SHALL display the exact `completed_count/total_count` value rather than a percentage.

#### Scenario: Display partial progress
- **WHEN** a task has completed 3 of 10 units
- **THEN** its user-facing progress value is `3/10`

#### Scenario: Complete a task
- **WHEN** a task finishes successfully
- **THEN** its completed count equals its total count and its progress value is the full `total/total` pair

### Requirement: Import progress remains non-blocking
The import progress stream SHALL report each item as completed after its file is stored and its task is created, without waiting for background task processing. Import progress SHALL display completed batch items over total batch items.

#### Scenario: Complete an import item
- **WHEN** a file is stored and its background task is created
- **THEN** the import item is marked completed and the import summary increments its completed-item count

#### Scenario: Display import progress
- **WHEN** 2 of 5 import items have been stored and assigned tasks
- **THEN** import progress displays `2/5`

### Requirement: Missing count data is not shown as a percentage
If a processing task has no usable count pair, the system SHALL NOT derive or display a fabricated percentage-based count pair. It SHALL present a non-numeric processing indication until a valid count pair is available.

#### Scenario: Handle an unavailable count pair
- **WHEN** a processing task has no completed count or has a non-positive total count
- **THEN** the progress surface shows a non-numeric processing indication instead of a percentage or fabricated `45/100` value

### Requirement: Progress bars reflect count completion
When a visual progress bar accompanies count-based progress, the system SHALL calculate its fill ratio from the completed and total counts and expose the count pair in progressbar accessibility attributes.

#### Scenario: Render an accessible progress bar
- **WHEN** a task has completed 4 of 8 units
- **THEN** the progress bar is 50% filled, has a maximum value of 8, a current value of 4, and accessible progress text `4/8`
