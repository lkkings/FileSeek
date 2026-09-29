## Why

图片搜索把 OCR 文本向量与图片向量放在同一个候选池中直接比较原始相似度分数。Jina CLIP 的文本到文本分数分布天然高于文本到图片分数，导致含 OCR 文本的图片系统性压过视觉上更匹配的图片。

## What Changes

- Preserve OCR extraction and indexing.
- Replace raw cross-modality score comparison with category-aware weighted ranking.
- When no category filter is present, text feature scores use a lower weight than image feature scores.
- When the category filter is image-only, OCR feature scores use a lower weight than image feature scores.
- Expose the selected match type in existing chunk metadata so the result detail can explain whether ranking came from visual or OCR content.
- For images with both feature types, the weighted OCR score participates in ranking without replacing the visual signal.
- Add focused tests covering unfiltered, image-only, mixed-category, and missing-feature cases.

## Capabilities

### New Capabilities

- `search/image-semantic-ranking`: Category-aware weighted ranking requirements for image semantic search, including image vectors, OCR text vectors, category filters, and weighted score aggregation.

### Modified Capabilities

- None. There is no existing main specification for image search ranking under `openspec/specs`.

## Impact

- Backend search ranking and result assembly.
- File chunk score and metadata handling.
- Existing image index remains compatible; no reindex or vector database schema migration is required.
- Tests for search use cases, API mappers, and image feature metadata.
