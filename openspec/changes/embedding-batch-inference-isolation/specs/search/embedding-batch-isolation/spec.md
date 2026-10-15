## Purpose

Defines deterministic embedding behavior for text and image inputs so indexing and query vectors do not depend on unrelated batch members or padding.

## ADDED Requirements

### Requirement: Embeddings are invariant to batch composition
The system SHALL produce the same embedding for the same text or image input whether that input is embedded alone or together with unrelated inputs.

#### Scenario: Image is embedded alone and with another image
- **WHEN** the same image is embedded once alone and once alongside an unrelated image
- **THEN** the resulting image embeddings are equal within floating-point tolerance

#### Scenario: Text is embedded alone and with another text
- **WHEN** the same text is embedded once alone and once alongside an unrelated text
- **THEN** the resulting text embeddings are equal within floating-point tolerance

### Requirement: Text embeddings are invariant to padding
The system SHALL ensure padding introduced to align a text batch does not change the embedding of any text in that batch.

#### Scenario: Short text is batched with a longer text
- **WHEN** a short text is embedded together with a longer text and therefore padded
- **THEN** its embedding equals the embedding produced for that short text alone within floating-point tolerance

#### Scenario: Texts have equal lengths
- **WHEN** multiple texts of equal token length are embedded together
- **THEN** each embedding equals the corresponding embedding produced for that text alone within floating-point tolerance

### Requirement: Query and indexing use isolated embeddings
The system SHALL use the same input-isolated embedding behavior for query text, document text, OCR text, images, and video frames.

#### Scenario: Query and indexed content use the inference path
- **WHEN** a semantic search embeds the query and compares it with indexed content vectors
- **THEN** both vectors are produced by the batch-isolated inference behavior

#### Scenario: Content is reprocessed after inference isolation
- **WHEN** text, image, or video content that was previously embedded in a multi-input batch is embedded again
- **THEN** the resulting vector is deterministic and independent of the original batch composition
