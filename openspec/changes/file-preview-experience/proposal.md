## Why

File lists currently use generic icons and simulated visuals, while the detail drawer does not render the actual file content. Users need trustworthy previews before opening files and consistent in-app viewing for documents, images, and videos.

## What Changes

- Add real preview rendering for file list rows and grid cards: document files show format-specific icons, images show image thumbnails, and videos show video-frame thumbnails with playback affordance.
- Render actual content in the file detail drawer: documents show the first page, images display the image, and videos show a thumbnail that can start an inline player.
- Add an application-internal full-screen/page viewer for opening files: documents use `anyview`, images use the image viewer, and videos use `video.js`.
- Add a backend thumbnail API for list and detail-sized image and video previews, with generation and caching behavior.
- Provide a binary preview transport that works in browser development and packaged Tauri builds without exposing the backend token to the WebView.
- Show accessible loading, fallback, and unsupported-format states instead of blank or misleading simulated previews.

## Capabilities

### New Capabilities

- `file-preview`: Defines file preview rendering, thumbnail retrieval, in-app opening behavior, format support, fallbacks, and transport requirements.

### Modified Capabilities

- None. The existing `recent/access-records` requirements do not change.

## Impact

- Frontend: add a `file-preview` feature and integrate it with `FileListRow`, `FileGridItem`, `FileDetailDrawer`, and the application viewer surface.
- Backend: add thumbnail generation and retrieval to the library file interface, reusing file lookup and the virtual filesystem.
- Desktop shell: add a secure binary preview transport for packaged Tauri builds while preserving the Vite development proxy.
- Dependencies: add `anyview` and the optional parsers needed for supported document formats; retain `video.js` and existing PDF/XLSX dependencies where compatible.
- Tests: cover preview format selection, thumbnails, drawer interactions, in-app opening, unsupported formats, and API/transport behavior.
