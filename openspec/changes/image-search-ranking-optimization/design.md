## Context

See `proposal.md` for the ranking bias being addressed.

The current image handler writes one image feature and optionally one OCR feature. Each feature record already carries `feature_type` in file chunk metadata, but search scores all chunks together and the result mapper chooses the highest raw score. This is invalid because Jina CLIP text-to-text and text-to-image cosine scores are not calibrated to the same scale.

## Goals / Non-Goals

**Goals:**

- Keep OCR indexing and make OCR an auxiliary ranking signal.
- Make unfiltered and image-only searches visually stable using category-aware weights.
- Preserve existing vector database records and API compatibility.
- Keep ranking deterministic and testable.

**Non-Goals:**

- Replacing the embedding model, OCR provider, or vector database.
- Building an offline relevance dataset or learned ranker in this change.
- Changing non-image semantic search ranking.
- Adding a new API request field; category filters already provide the needed ranking context.

## Decisions

### Use category-aware weights

Use the request’s category filter to choose feature weights:

- No category filter or a mixed category filter: image feature weight `1.0`, text feature weight `0.6`.
- Image-only category filter: image feature weight `1.0`, OCR feature weight `0.4`.

These weights are implementation constants, not user-facing configuration. They reduce the natural text-score advantage while preserving OCR as an auxiliary signal.

### Use weighted max aggregation

For each image file, compute:

`weighted_score = max(image_score, ocr_score * ocr_weight)`

If the file has no OCR feature, use `image_score`. If the file has no image feature, use `ocr_score * ocr_weight`.

This prevents a high raw OCR score from replacing a strong visual match while still allowing OCR to help images with weak visual relevance.

### Keep raw scores for diagnostics

Store the raw vector score on the selected chunk and use the weighted score for file ranking. This keeps the response score interpretable while avoiding cross-modality score bias.

### Preserve response shape

Return the selected match type in existing chunk metadata. Add no required response field, so existing clients remain compatible.

## Risks / Trade-offs

- [Risk] Fixed weights may over- or under-correct for some query types. → Start with conservative values and revisit after observing real search quality.
- [Risk] Weighted max can still favor OCR for visually weak matches. → The image-only OCR weight is intentionally lower than the unfiltered text weight.
- [Risk] Legacy chunks missing `feature_type` metadata cannot be assigned confidently. → Treat only records explicitly marked `ocr` as the OCR channel; all other image-file records are visual candidates.

## Migration Plan

1. Introduce category-aware feature weights in the search ranking path.
2. Update result assembly to use the weighted selected chunk.
3. Add tests while preserving the existing default search contract.
4. Roll back to the original result path if ranking regresses; vector data remains unchanged.
