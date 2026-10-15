## Why

Real-model diagnostics show that jina-clip-v2 ONNX inference is not batch-isolated: embeddings for the same image can change when it is inferred together with other images, and text batches are padded without an attention mask. This can silently alter indexed document, video, and OCR vectors even though the source content is unchanged.

## What Changes

- Add a focused diagnostic proving whether batch size and batch composition change embeddings for the same input.
- Require image and text embeddings to be invariant to unrelated batch members and padding.
- Fix the ONNX inference path so production indexing and query embeddings satisfy that invariant.
- Add regression coverage using deterministic synthetic inputs and, when the model is cached, real-model parity tests.
- Document whether existing indexed vectors require reindexing after the fix.

## Capabilities

### New Capabilities

- `search/embedding-batch-isolation`: Requirements for deterministic, batch-isolated text and image embeddings used by indexing and search.

### Modified Capabilities

- None. There is no existing main specification for embedding inference behavior.

## Impact

- Backend embedding adapter and inference batching.
- Document, image OCR, video, and query embedding paths.
- Backend tests for embedding inference and handlers that rely on batched inference.
- Existing vector index compatibility and possible reindexing guidance; no API contract change is planned.
