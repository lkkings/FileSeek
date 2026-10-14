## Why

Nuitka standalone bundles 631 MB of backend and dependencies into every signed app update and adds about 25 minutes to each platform build. The backend source is only 3.2 MB, so shipping protected source with the app and downloading the pinned Python runtime only when dependencies change gives much smaller code-only updates while preserving deterministic, hash-verified first-run setup.

This change replaces the completed-but-unarchived Nuitka direction before it becomes the release baseline. It restores the dependency-download architecture already explored in `commercial-licensing-and-updates`, fixes the model manifest's missing content identity, and makes model changes trigger a new download set.

## What Changes

- Remove the Nuitka standalone backend from release packaging; app updates carry a small protected backend package instead.
- Protect backend source with PyArmor, pending a platform/runtime compatibility spike; the spike may select compiling selected modules as the fallback if PyArmor cannot support FastAPI, spawned model workers, onnxruntime, and chromadb.
- Restore first-run and post-update download of a pinned Python interpreter and every backend dependency wheel from official sources or mirrors.
- Derive `runtime_id` from normalized `uv.lock`, Python version, and python-build-standalone release; code-only updates reuse the installed runtime, while dependency changes install a new one atomically and retain the previous one for rollback.
- Keep the protected backend package inside the signed Tauri app update rather than downloading it from a separate unsigned source.
- Replace the current fixed model id with a `model_set_id` derived from the canonical model file manifest; any file hash change creates a new model directory and requires download/verification before switching.
- **BREAKING** relative to `backend-nuitka-gpu-acceleration`: release packaging again downloads interpreter, wheels, and model on first run instead of only the model.
- **BREAKING** relative to the current model layout: model directories are keyed by model set identity, not the stable `jina-clip-v2-q` label.

## Capabilities

### New Capabilities
- `backend-runtime`: Download, verify, atomically install, reuse, and roll back the pinned Python interpreter and dependency wheel set required by the protected backend.
- `backend-code-protection`: Package the backend source in a protected form that starts with the downloaded runtime and does not ship plaintext source, while treating protection as tamper resistance rather than a licensing-security boundary.
- `model-sets`: Manage model downloads by content-defined model set identity, reusing an unchanged set and atomically switching to a newly hashed set after successful verification.

### Modified Capabilities
- None. No related capability has yet been archived; this change supersedes the unarchived `backend-nuitka-gpu-acceleration` capabilities and reconciles the unarchived `commercial-licensing-and-updates` backend-runtime requirements.

## Impact

- Backend: replace `build_nuitka.py` and `scripts/smoke_compiled.py` with a PyArmor/protected-source build and smoke flow; add any required protection runtime dependency without adding it to the application dependency closure unless needed at runtime.
- Desktop runtime: restore interpreter and wheel manifest parsing, `runtime_id`, space checking, download, staging, atomic install, cleanup, and repair in `desktop/src-tauri/src/runtime/`.
- Sidecar/readiness: start downloaded Python against the protected backend resource with an isolated environment; initialize model sets before startup.
- Release manifests: regenerate platform source lists from `uv.lock`, `runtime.json`, and the model manifest; compile them into the app.
- CI/release: remove the Nuitka cache and standalone smoke test; add protected-backend packaging and runtime download/install tests.
- User experience: first run again requires interpreter, wheels, and model downloads; code-only updates do not redownload an unchanged runtime, and model hash changes redownload the changed model set.
