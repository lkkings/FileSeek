## Purpose

Defines category-aware weighted ranking for image semantic search so visual and OCR text signals remain useful without letting incompatible similarity-score distributions dominate one another.

## ADDED Requirements

### Requirement: Search applies category-aware feature weights
The system SHALL assign feature weights based on the request’s category filter. Text feature scores SHALL be weighted lower than image feature scores when no category filter is present.

#### Scenario: No category filter is present
- **WHEN** a semantic search request has no category filter
- **THEN** text feature scores are multiplied by a lower weight than image feature scores before ranking

#### Scenario: Category filter includes non-image categories
- **WHEN** a semantic search request includes image and non-image categories
- **THEN** text feature scores use the unfiltered-search weight

### Requirement: Image-only search lowers OCR weight
When the category filter is image-only, the system SHALL rank image files using image feature scores with a higher weight than OCR feature scores.

#### Scenario: Image-only search with OCR
- **WHEN** an image-only semantic search request matches an image through both visual and OCR features
- **THEN** the OCR score is multiplied by a lower weight before it participates in ranking

#### Scenario: Image-only search without OCR
- **WHEN** an image-only semantic search request matches an image only through visual content
- **THEN** ranking uses the unweighted image feature score

### Requirement: Weighted OCR participates without replacing visual ranking
For an image with both visual and OCR features, the system SHALL use the weighted OCR score as an auxiliary ranking signal, not as an unweighted replacement for the visual score.

#### Scenario: OCR raw score is higher than image score
- **WHEN** an image’s OCR cosine score is higher than its image cosine score
- **THEN** ranking reflects the weighted OCR score rather than the raw OCR score

#### Scenario: Visual score is stronger
- **WHEN** an image’s visual score is stronger than its weighted OCR score
- **THEN** ranking uses the visual score

### Requirement: Weighted results expose the selected match type
For image results assembled from weighted ranking, the system SHALL include a machine-readable match type indicating whether the result was ranked by the image feature or OCR feature.

#### Scenario: Result is ranked visually
- **WHEN** an image result is selected using the image feature score
- **THEN** its returned metadata identifies a visual match

#### Scenario: Result is ranked by OCR
- **WHEN** an image result is selected using the weighted OCR feature score
- **THEN** its returned metadata identifies an OCR match

### Requirement: Existing image indexes remain compatible
The system SHALL implement category-aware weighted image ranking using existing image and OCR feature records and SHALL NOT require rebuilding the vector index.

#### Scenario: Existing image feature records are present
- **WHEN** an image file already has one image feature record and one OCR feature record from the current indexing flow
- **THEN** weighted ranking uses those records without reindexing the file
