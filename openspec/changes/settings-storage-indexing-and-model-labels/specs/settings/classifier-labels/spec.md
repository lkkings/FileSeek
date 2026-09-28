## Purpose

Provides a backend-managed label vocabulary that controls which document, image, and video labels the model classifier may emit.

## ADDED Requirements

### Requirement: Read classifier label vocabulary
The system SHALL expose the current document, image, and video label vocabulary to the settings UI.

#### Scenario: Read labels
- **WHEN** the settings UI requests the classifier label vocabulary
- **THEN** the system returns the current labels grouped by document, image, and video category

### Requirement: Replace classifier label vocabulary
The system SHALL allow an authenticated settings client to replace the complete classifier label vocabulary.

#### Scenario: Replace labels
- **WHEN** the settings client submits a valid vocabulary containing document, image, and video labels
- **THEN** the system stores the submitted vocabulary and returns the saved vocabulary

#### Scenario: Reject duplicate category labels
- **WHEN** a submitted vocabulary contains the same label more than once within one category
- **THEN** the system rejects the update and leaves the existing vocabulary unchanged

### Requirement: Classifier uses the current vocabulary
The system SHALL use the current classifier label vocabulary for classification tasks that start after the vocabulary has been updated.

#### Scenario: New task uses updated labels
- **WHEN** a file processing task starts after a label vocabulary update
- **THEN** the model classifier only considers labels from the updated vocabulary for that task

#### Scenario: In-flight task keeps its label snapshot
- **WHEN** a label vocabulary update occurs while a file processing task is already running
- **THEN** the in-flight task completes with the vocabulary it started with

### Requirement: Vocabulary is independent from file tags
The classifier label vocabulary SHALL NOT modify, validate, or delete existing tags already assigned to indexed files.

#### Scenario: Remove a vocabulary label
- **WHEN** a label is removed from the classifier vocabulary
- **THEN** existing file tags with the same text remain unchanged
