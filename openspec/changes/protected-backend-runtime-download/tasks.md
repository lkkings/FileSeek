## 1. Protected backend spike and packaging

- [x] 1.1 Add a pinned PyArmor development dependency and a backend build script that stages obfuscated backend entry points, the PyArmor runtime package, and required non-Python package data without plaintext `.py` files. Verify by inspecting the staged output and running its backend entry point.
- [x] 1.2 Adapt the backend smoke script to start the protected package with a real Python runtime and verify `/health`, connection-file publication, and the expected process topology. Verify with `backend/scripts/smoke_protected.py`.
- [x] 1.3 Run an import and query workload through the protected package, including onnxruntime, chromadb, RapidOCR data, and multiprocessing `spawn` workers. Verify a test image import, image embedding, and text search succeed with only the main process listening on the API port.
- [x] 1.4 Start the protected backend with conflicting `PYTHONHOME`, `PYTHONPATH`, and `VIRTUAL_ENV` values. Verify the process still uses the staged protected package and downloaded runtime.

## 2. Runtime source manifests

- [x] 2.1 Restore Python interpreter, mirror, and model configuration to `release/runtime.json` with pinned versions, sizes, and SHA-256 values. Verify the file parses and contains all four supported target configurations.
- [x] 2.2 Restore `release/runtime_id.py` and its cross-language test so normalized `uv.lock`, Python version, and python-build-standalone release produce one stable identifier. Verify the Python and Rust calculations match.
- [x] 2.3 Rewrite `release/build_sources.py` to emit manifest version 4 with the interpreter, exact platform-specific wheel closure, `runtime_id`, unpacked-size estimate, and the new model set identity. Verify `--check` passes after generating all target files.
- [x] 2.4 Compare the generated wheel closure with `uv`'s resolved production dependency set for macOS arm64 and Windows x64. Verify there are no missing or extra production packages.

## 3. Desktop runtime download and installation

- [x] 3.1 Restore manifest structures and parsing for interpreter, wheels, `runtime_id`, and model sets. Verify manifest tests reject stale versions, unsupported targets, malformed lists, and missing official sources.
- [x] 3.2 Implement runtime readiness, resumable downloads, checksum verification, space checking, staging extraction, offline pip installation, `.complete`, and atomic rename. Verify tests cover mirror checksum mismatch, interrupted transfer, failed install, and successful atomic install.
- [x] 3.3 Implement runtime reuse, new-runtime installation, previous-runtime retention, stale-runtime cleanup, and runtime repair. Verify tests show a code-only update makes no network requests and a dependency update retains one rollback runtime.
- [x] 3.4 Restore the production sidecar command to launch the downloaded interpreter against the protected backend resource with an isolated environment. Verify sidecar tests cover conflicting Python variables and the model cache environment variable.
- [x] 3.5 Measure mirror throughput and try runtime, dependency, and model sources fastest-first while retaining hash verification and official-source fallback. Verify mirror ranking prefers a responsive source over an unavailable one.

## 4. Model set management

- [x] 4.1 Add canonical `model_set_id` calculation to release manifest generation and desktop manifest structures. Verify a changed path, size, or SHA-256 produces a different identity while a URL-only change does not.
- [x] 4.2 Change model installation and `current.json` selection to use model set identity with atomic switching and previous-set retention. Verify tests cover unchanged-set offline reuse, changed-hash redownload, failed new-set download, and successful switch.
- [x] 4.3 Update model repair to hash files against the current model set, delete only mismatched files, and preserve the rollback set. Verify the existing damaged-model repair test covers same-size wrong content and resumes only missing files.
- [x] 4.4 Add cleanup for stale model sets and staging directories while retaining the selected and previous complete sets. Verify tests prove a failed download never deletes the selected set.

## 5. Release packaging and CI

- [x] 5.1 Replace Nuitka staging in `desktop/scripts/stage-backend.mjs` with protected-backend staging and remove the standalone size limit and Nuitka cache. Verify `pnpm run build` produces the protected backend resource without `.py` source files.
- [x] 5.2 Update release workflow comments and smoke-test jobs to build protected source, generate/check runtime sources, and test the downloaded-runtime startup path on macOS arm64 and Windows x64. Verify the workflow includes both platform matrix legs.
- [x] 5.3 Remove or archive the now-unused Nuitka build and compiled smoke scripts. Verify repository searches find no release-path reference to `build_nuitka.py` or `smoke_compiled.py`.
- [x] 5.4 Update the unarchived `backend-nuitka-gpu-acceleration` and `commercial-licensing-and-updates` artifacts to state that this change supersedes the Nuitka packaging direction. Verify the supersession notes agree across proposal and spec files.

## 6. End-to-end validation

- [ ] 6.1 Run backend formatting, lint, type checking, and unit tests. Verify `ruff`, `mypy`, and `pytest` pass.
- [x] 6.2 Run desktop Rust and frontend checks. Verify `cargo test`, frontend type checks, and frontend unit tests pass.
- [ ] 6.3 Exercise a clean data directory on macOS: activate, download runtime and model, reach ready, import an image, run text and image searches, restart offline, and verify no second download. Verify logs and readiness states follow the designed order.
- [x] 6.4 Simulate a code-only app update and a dependency-changing update. Verify only the dependency-changing update downloads a runtime and both retain rollback data.
- [x] 6.5 Simulate a model file hash change and a damaged local model file. Verify the hash change installs a new model set before switching and repair replaces only the damaged file.
