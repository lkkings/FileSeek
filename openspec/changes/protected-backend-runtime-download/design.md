## Context

The current release branch implements the unarchived Nuitka change: `desktop/scripts/stage-backend.mjs` compiles a 631 MB standalone directory, the app starts its embedded executable, and first-run initialization downloads only the model. Earlier work in `commercial-licensing-and-updates` already designed and largely implemented a downloaded runtime: python-build-standalone, a platform-specific wheel list derived from `backend/uv.lock`, SHA-256 verification, and atomic installation by `runtime_id`.

The backend source tree is 3.2 MB. Release code can therefore remain inside the signed Tauri update while interpreter and dependencies move back to user data. The model downloader already has resumable transfers and digest checks, but it identifies the model by the stable label `jina-clip-v2-q`, which does not change when a pinned file digest changes.

## Goals / Non-Goals

**Goals:**
- Keep app and code-only update artifacts small.
- Revert standalone backend bundling and restore reusable, pinned runtime downloads.
- Ensure a model manifest digest change always installs a different model set.
- Keep source out of plaintext release bundles without moving licensing trust into Python.
- Preserve development execution with `uv run`.

**Non-Goals:**
- Strong DRM or preventing a determined user from reverse engineering local code.
- GPU acceleration, delta updates, or background pre-download of the next runtime.
- Rehosting interpreter, wheel, or model files on FileSeek infrastructure.
- Full content digest verification of the 874 MB model on every normal startup.
- Linux release support.

## Decisions

### 1. Protected backend package: PyArmor first

Use a pinned PyArmor build to transform the backend package into obfuscated scripts plus the required PyArmor runtime package, and stage that output under the app's backend resource directory. The desktop app will start the downloaded Python interpreter with the protected resource directory on `PYTHONPATH`.

The spike must prove the protected package works on macOS arm64 and Windows x64 with:

- FastAPI startup and `/health`
- multiprocessing workers using the spawn start method
- onnxruntime model import and query
- chromadb and its dynamically imported implementation
- RapidOCR package data
- a host environment containing conflicting `PYTHONHOME`, `PYTHONPATH`, and `VIRTUAL_ENV`

Do not enable anti-debug, expiry, or device-binding features in this change. They add false positives and do not establish the licensing trust boundary. If the PyArmor spike fails, stop and revise this change rather than silently substituting another protector; the only acceptable short fallback is compiling selected application modules while retaining downloaded dependencies, and that requires a new explicit decision.

**Alternative rejected: Nuitka standalone.** It removes source and avoids runtime download, but it makes every code-only app update carry the full dependency closure and lengthens CI.

**Alternative rejected: plaintext `.pyc`.** It removes casual source readability but is straightforward to decompile and does not meaningfully protect application code.

### 2. Runtime identity and installation

Restore the runtime source-list generator and desktop runtime modules from the downloaded-runtime design. Use manifest version 4 so old app builds cannot misread the new format. Runtime and model downloads measure each distinct source origin once with a 64 KiB range request, cache the measured speed, and try sources fastest-first; probes never replace the full size and SHA-256 verification.

`runtime_id` SHALL be:

```text
rt- + first 16 hex chars of SHA-256(
    LF-normalized backend/uv.lock bytes
    + NUL + Python version
    + NUL + python-build-standalone release
)
```

The source generator SHALL resolve the production dependency closure per target using environment markers and wheel tags. It SHALL list the exact interpreter archive and every wheel with size, SHA-256, source URLs, expected interpreter path, and unpacked-size estimate. The generated list is compiled into the signed app.

Installation SHALL:

1. Download and verify each file to a staging area.
2. Extract the interpreter.
3. Run its bundled pip with `--no-index --no-deps` against only the verified wheel files.
4. Verify the expected interpreter and installed package importability markers needed by the app.
5. Write `.complete`.
6. Rename the staging directory to `<data_dir>/runtime/<runtime_id>/`.
7. Keep the previous runtime and remove only older directories.

Dependency resolution happens at build time, not on the user's machine. The app never invokes pip against a live index.

### 3. Code updates and runtime updates

The Tauri update continues to carry only the signed app package, including the protected backend. After the update restarts, readiness compares the app's embedded `runtime_id` with the installed runtime:

```text
same runtime_id      -> start protected backend with installed runtime
different runtime_id -> download/install new runtime, then start backend
```

No pre-update runtime download is introduced. The previous runtime remains on disk so an app rollback to the older signed app can use its old `runtime_id` immediately.

### 4. Model set identity

Introduce `model_set_id` separate from the human-readable model id:

```text
ms- + first 16 hex chars of SHA-256(canonical JSON({
    id,
    files: [{path, size, sha256}]
}))
```

The identity excludes source URLs and upstream source paths. Mirror or URL changes do not invalidate an already verified local file set; only local expected content changes do.

Model files install under `<data_dir>/models/<model_set_id>/`. `current.json` records the selected `model_set_id`. A changed digest, changed local path, or changed size produces a new directory and requires a complete verified download before the app switches `current.json`.

Normal startup checks the complete marker and recorded file sizes, not the full 874 MB digest. Full digest checking remains part of model repair and is used to remove only files that no longer match the current model set. Keep the selected set and the immediately previous complete set; remove older sets only after successful selection of the new one.

### 5. Readiness ordering

The state machine remains Rust-owned:

```text
license check -> activation -> runtime check
    -> space check -> downloading -> verifying -> installing
    -> model check/download -> starting -> ready
```

Runtime and model initialization remain after licensing so unlicensed users do not download large binaries. The UI reports one aggregate progress total across runtime and model files while preserving the existing phase events. Failed initialization offers retry, and backend startup failure offers repair for the runtime or model as appropriate.

## Risks / Trade-offs

- [PyArmor incompatibility with spawn workers or dynamic imports] -> Run the platform spike before removing Nuitka; make the spike a blocking task.
- [First run becomes large again] -> Show combined download size before starting and preserve resumable transfers.
- [Protected Python can still be instrumented] -> Keep licensing and update trust in compiled Rust and server-side verification.
- [Wheel closure drift between platforms] -> Generate and check per-target manifests in CI and compare the resolved package set with `uv`.
- [Runtime download failure blocks use after a code-only update] -> Reuse unchanged `runtime_id`; only dependency changes require a new runtime.
- [Hash-only model identity could accidentally reuse a wrong same-size file] -> Use the new model set identity, verify digests on download and repair, and never mark a set complete after an unverified transfer.
- [Rollback disk use grows] -> Retain only the current and one previous runtime/model set and clean stale staging directories at startup.

## Migration Plan

1. Run the PyArmor compatibility spike against the current backend.
2. Restore runtime manifest generation and desktop runtime download/install logic.
3. Introduce `model_set_id` and migrate `current.json`; do not delete existing model directories until the new set is complete.
4. Replace Nuitka staging and compiled-backend smoke tests with protected-source staging and runtime-backed smoke tests.
5. Update the two unarchived Nuitka/commercial change artifacts to record that this change supersedes the Nuitka release direction.
6. Rollback is the previous signed app plus retained old runtime/model set; no data migration is required beyond adding the new current-model record.
