## Context

See `proposal.md` for the observed failure. The current adapter groups inputs before ONNX inference. The exported model exposes only `input_ids` and `pixel_values`; it does not expose an attention mask. Real-model diagnostics showed that a two-image batch changes each image vector relative to single-image inference, and padded text batches change short-text vectors relative to single-text inference.

The image preprocessing path is already parity-checked against the official Jina processor, and the query tokenizer path is parity-checked against the official tokenizer. The remaining correctness boundary is ONNX batch execution.

## Goals / Non-Goals

**Goals:**

- Make embeddings deterministic and independent of unrelated batch members and padding.
- Apply the same behavior to query, document, OCR, image, and video inference.
- Add fast synthetic tests and model-cached regression tests.
- Quantify the performance cost of the isolation strategy.
- Decide and document whether existing indexes need rebuilding.

**Non-Goals:**

- Replacing the embedding model or vector database.
- Changing search ranking, relevance thresholds, or API contracts.
- Optimizing model loading or process isolation.
- Regenerating or patching the ONNX graph in this change.

## Decisions

### Make one input the correctness baseline

Process each text and image independently at the ONNX inference boundary. Reintroduce batching only if a future model graph explicitly guarantees sample isolation and, for text, provides a supported masking mechanism.

This is intentionally conservative: it immediately guarantees the behavior contract without depending on assumptions about the exported graph. The cost is additional ONNX calls, which must be measured for document and video indexing.

Alternative: group texts by equal token length. This removes padding differences but does not address the observed cross-sample effect for different images and may still expose text cross-sample effects.

Alternative: add attention masking. The current ONNX graph does not accept an attention mask, so this requires a new graph and is out of scope.

### Keep the public embedding API batch-shaped

Keep `embed_text` and `embed_image` accepting lists and preserving input order. Internally, iterate over items and invoke ONNX one item at a time. This minimizes changes to callers while making the contract explicit.

Alternative: force every caller to loop. That spreads the invariant across document, image, OCR, and video code and makes future regression easier.

### Add two levels of regression coverage

Use deterministic fake ONNX sessions to verify that batching does not alter the tensors sent for each item and that output order is preserved. Add slow, model-cached tests that compare single-input embeddings with mixed-input batches for both modalities.

The real-model test is the guard against silently reintroducing graph-level cross-sample behavior.

### Do not automatically rebuild existing vectors in this change

After isolation is implemented, existing document and video vectors remain in place. They are potentially stale because they may have been produced by multi-input inference, but automatic rebuild would make startup time unpredictable and a new UI would expand this change beyond the inference defect.

Image and image-OCR vectors are currently produced in single-item calls. New and reprocessed content uses isolated inference immediately. A separate user-triggered reindex capability should be proposed after this change so users can refresh existing document and video vectors deliberately.

## Risks / Trade-offs

- [Risk] One-item inference is slower for documents and videos. → Benchmark representative workloads before finalizing; keep the model process architecture unchanged.
- [Risk] Existing search behavior changes after vectors are rebuilt. → Compare a fixed query set before and after reindex and record the outcome.
- [Risk] Real-model tests are unavailable on machines without the cached model. → Keep them slow and skipped by default; use fake-session tests for CI.
- [Risk] A future model update may reintroduce batching assumptions. → Retain the mixed-batch parity test as an acceptance requirement.

## Migration Plan

1. Add the single-input inference behavior and regression tests without changing stored data.
2. Benchmark representative document, video, image, and query workloads.
3. Validate search quality on a fixed query set using newly indexed content.
4. Record the migration limitation and propose a separate user-triggered reindex capability.
5. Roll back the adapter change if needed; no database schema migration is required.

## Performance Measurements

The representative benchmark ran on the local development machine (Apple M5, Darwin arm64) with the cached quantized ONNX model. Each mode used 5 timed runs after 2 warmup runs and compared two inputs.

| Mode | Isolated | Previous batched | Mean delta |
| --- | --- | --- | --- |
| Text: 2 calls vs 1 padded call | 20.22 ms | 21.35 ms | -1.13 ms |
| Image: 2 calls vs 1 call | 2,097.04 ms | 2,105.41 ms | -8.37 ms |

For this model and sample size, the additional ONNX calls were offset by the smaller per-call tensor work. Isolation did not measurably increase inference latency; larger batches may show a different trade-off and can be benchmarked before reintroducing batch execution.

## Open Questions

None.
