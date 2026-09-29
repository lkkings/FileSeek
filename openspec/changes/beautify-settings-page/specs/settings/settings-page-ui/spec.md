## Purpose

Defines the visible hierarchy, responsive layout, and presentation-state behavior for the desktop settings page so its language, tag, and storage areas work as one coherent interface.

## ADDED Requirements

### Requirement: Settings page provides a clear hierarchy
The settings page MUST present a localized page title and subtitle above its setting groups, and the three existing setting groups MUST remain identifiable and reachable in the page order language, tags, then storage.

#### Scenario: Desktop hierarchy
- **WHEN** the settings page is displayed at a desktop viewport width
- **THEN** the page title and subtitle appear above the setting groups
- **AND** language settings occupy a compact secondary column beside the tag-management area
- **AND** storage management spans the content width below them

#### Scenario: Narrow viewport hierarchy
- **WHEN** the settings page is displayed at a narrow viewport width
- **THEN** the page header and setting groups stack without horizontal overflow
- **AND** the setting groups remain ordered language, tags, then storage

#### Scenario: Localized page header
- **WHEN** the user switches the interface language
- **THEN** the settings page title and subtitle update in the selected language

### Requirement: Settings groups use a coherent visual system
The settings page MUST style cards, controls, inputs, chips, rows, badges, and section furniture with one consistent visual system that supports the application's dark theme without making decoration compete with the settings content.

#### Scenario: Setting groups are visually related
- **WHEN** the settings page is displayed
- **THEN** each setting group uses related surface, border, spacing, corner-radius, text, and accent treatments
- **AND** primary actions, secondary controls, and status badges have visually distinct treatments

#### Scenario: Storage groups remain scannable
- **WHEN** storage settings contain local storage, NAS storage, or an add-drive form
- **THEN** local and NAS groups are visually separated and each storage row clearly communicates its name, protocol, endpoint, status, and available actions

### Requirement: Settings presentation states are understandable
The settings page MUST clearly distinguish interactive, disabled, loading, empty, successful, and error presentation states while preserving the existing interactive semantics and localized labels.

#### Scenario: Non-interactive storage control
- **WHEN** a storage action is unavailable because it is disabled
- **THEN** its control is visibly non-interactive and retains its accessible disabled state

#### Scenario: Feedback states
- **WHEN** settings are loading, empty, submitted successfully, or submission fails
- **THEN** the page communicates that state in context without replacing unrelated setting groups
- **AND** the message remains localized and readable
