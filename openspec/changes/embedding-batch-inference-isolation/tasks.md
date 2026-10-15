## 1. Diagnostics

- [x] 1.1 Add a deterministic embedding test that captures the tensors submitted for each text and image item; verify mixed batch calls submit one item per inference call and preserve output order.
- [x] 1.2 Add model-cached slow tests comparing single-input embeddings with mixed-input image and padded-text batches; verify each embedding is equal within floating-point tolerance.

## 2. Inference Isolation

- [x] 2.1 Update the jina-clip-v2 adapter to run ONNX inference one text or image item at a time while preserving the public list API; verify focused unit tests pass.
- [x] 2.2 Remove obsolete text batch planning and padding behavior from the inference path; verify tests prove short text is no longer padded to another item's length.
- [x] 2.3 Keep query and indexing call sites unchanged; verify backend tests for query embedding, document handling, image handling, and video handling still pass.

## 3. Performance And Migration

- [x] 3.1 Benchmark representative single-item versus previous batched inference for text and images; record the measured cost in the design document.
- [x] 3.2 Document that existing vectors are not automatically rebuilt and that a separate user-triggered reindex change is required; verify the design records the migration decision.

## 4. Validation

- [x] 4.1 Run the focused embedding and affected handler tests; verify `uv run --directory backend pytest tests/infrastructure/test_jina_clip_v2_embedding.py tests/infrastructure/test_embedding_batch_isolation.py tests/infrastructure/test_clip_preprocess.py tests/infrastructure/test_clip_tokenizer.py` passes.
- [x] 4.2 Run backend static checks for modified files; verify `uv run --directory backend ruff check src/fileseek/infrastructure/embedding tests/infrastructure` reports no findings.
- [x] 4.3 Validate the OpenSpec change; verify `openspec validate --strict embedding-batch-inference-isolation` passes.
