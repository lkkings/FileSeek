## 1. Dependencies and Foundations

- [x] 1.1 Add `anyview` and required format parsers to the desktop dependency manifest, then verify install and lockfile updates succeed without peer conflicts.
- [x] 1.2 Create the `file-preview` feature structure with format classification, preview URL construction, and public exports; verify unit tests cover supported and unsupported formats.
- [x] 1.3 Add document-format icon mapping and preview state helpers; verify rendering tests identify PDF, DOCX, XLSX, PPTX, text, and unsupported legacy formats.

## 2. Backend Thumbnails

- [x] 2.1 Implement image and video thumbnail generation with bounded dimensions and WebP encoding; verify unit tests cover resize and generation failure.
- [x] 2.2 Implement metadata-keyed caching and cache invalidation for changed files; verify repeated requests reuse cached bytes.
- [x] 2.3 Add the authenticated thumbnail route and use-case wiring for list/detail sizes; verify API tests cover success, unknown file, invalid category, and inaccessible source.
- [x] 2.4 Verify thumbnail responses include content type, cache metadata, and errors that do not expose source paths.

## 3. Frontend Preview Components

- [x] 3.1 Implement the shared list/grid preview cell with lazy image loading, video playback affordance, loading, and fallback states; verify component tests for each category and failure case.
- [x] 3.2 Replace simulated previews in `FileListRow` and `FileGridItem` with the shared preview cell; verify search, recent, and library list tests still pass.
- [x] 3.3 Implement first-page document preview in `FileDetailDrawer` with AnyView and no viewer chrome; verify drawer tests for supported and unsupported documents.
- [x] 3.4 Implement image and video previews in `FileDetailDrawer`, including click-to-play video.js mounting and cleanup; verify drawer interaction tests.
- [x] 3.5 Implement the full-screen in-app document, image, and video viewers; verify open-action tests for each category and unsupported documents.
- [x] 3.6 Route file open actions to the in-app viewer instead of the operating system; verify existing double-click/open callback tests are updated and pass.

## 4. Desktop Binary Transport

- [x] 4.1 Add runtime-aware preview URL resolution for Vite development and packaged Tauri modes; verify unit tests cover both URL forms.
- [x] 4.2 Implement the Rust-side preview protocol that forwards only approved preview requests with backend authentication; verify unit tests for allowed paths and rejected paths.
- [x] 4.3 Preserve `Range`, content type, content length, and cache headers through the preview transport; verify video seeking and binary response tests.
- [x] 4.4 Confirm the backend token is not exposed to WebView JavaScript by inspecting the frontend bundle and transport implementation.

## 5. Accessibility and Localization

- [x] 5.1 Add Lingui strings and accessible labels for loading, fallback, unsupported, play, open, and viewer controls; verify i18n rendering tests.
- [x] 5.2 Verify keyboard and screen-reader affordances for preview cells, video playback, viewer opening, and viewer closing.

## 6. Validation

- [x] 6.1 Run focused backend thumbnail API tests and confirm all preview-related backend tests pass.
- [x] 6.2 Run focused frontend preview component and viewer tests and confirm all affected feature tests pass.
- [x] 6.3 Run desktop typecheck and lint, fixing only issues introduced by this change.
- [ ] 6.4 Perform a development smoke test covering one document, image, and video from list preview through full-screen opening.
- [ ] 6.5 Perform a packaged-build smoke test verifying binary previews, video seeking, and secure token handling.
