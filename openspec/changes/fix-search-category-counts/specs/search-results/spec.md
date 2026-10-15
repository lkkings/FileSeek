## Purpose

Defines resource-library search result totals and per-category counts so users can compare available result types while browsing a filtered result set.

## ADDED Requirements

### Requirement: Category counts remain stable across resource type selection
The system SHALL compute category counts using all search filters except the resource type filter.

#### Scenario: Selecting images does not zero document counts
- **WHEN** the user searches with the image resource type selected and the search scope contains matching documents
- **THEN** the returned document count is greater than zero
- **AND** the returned image count reflects the matching images in that same search scope

#### Scenario: Changing resource type does not alter category counts
- **WHEN** the user changes only the selected resource type between two otherwise identical searches
- **THEN** the returned count for each category is the same in both responses

### Requirement: Search result total follows the selected resource type
The system SHALL return a result total for only the selected resource types, while category counts describe all resource types in the same search scope.

#### Scenario: Image-only search is paginated by image results
- **WHEN** the user searches with only the image resource type selected
- **THEN** the returned total equals the image count
- **AND** pagination is based on that total
- **AND** returned document counts are unaffected by the image-only selection
