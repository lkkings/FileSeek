## 1. Ranking Weights

- [x] 1.1 Implement category-aware feature weights for unfiltered, mixed-category, and image-only requests; verify unit tests cover all three filter states.
- [x] 1.2 Implement weighted max aggregation for images with both visual and OCR features; verify tests prove raw OCR scores cannot dominate visual scores.
- [x] 1.3 Preserve raw vector scores for diagnostics while using weighted scores for ranking; verify tests assert both values remain available where applicable.

## 2. Result Assembly

- [x] 2.1 Update semantic result assembly to use the weighted selected chunk for image results; verify unit tests cover selected chunk, score, and match-type metadata.
- [x] 2.2 Preserve existing behavior for files without image feature metadata and non-image categories; verify regression tests cover missing metadata and document-only searches.

## 3. Tests

- [x] 3.1 Extend search use-case tests for unfiltered, image-only, mixed-category, and OCR-only image matches; verify the targeted pytest suite passes.
- [x] 3.2 Add a regression test demonstrating that OCR indexing remains unchanged and no vector reindex is required; verify the image-handler feature metadata test passes.

## 4. Validation

- [x] 4.1 Run backend static checks for modified search files; verify `uv run --directory backend ruff check` reports no new findings.
- [x] 4.2 Run the focused backend search/task tests; verify `uv run --directory backend pytest tests/search tests/tasks/test_document_handler_classifier_snapshot.py` passes.
- [x] 4.3 Run `openspec validate --strict image-search-ranking-optimization`; verify the change artifacts pass validation.
