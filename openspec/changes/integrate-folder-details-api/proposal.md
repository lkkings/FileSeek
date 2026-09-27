## Why

Currently, `FolderDetailsView.tsx` uses mock/hardcoded data (`INITIAL_FILES`) for listing files inside a folder. To support real-world file browsing within indexed folders, the desktop frontend must integrate with the actual backend. The backend does not have a dedicated folder-contents listing API, but has a flexible `/api/v1/search` endpoint. Using `/api/v1/search` with an empty query and specific `folder_id` will retrieve all indexed files for that folder, supporting categories and tags filters natively without backend modifications.

## What Changes

- **Integrate Real API for Folder Details**: Replace `INITIAL_FILES` state inside `FolderDetailsView.tsx` with a dynamic TanStack Query or API fetch targeting the `POST /api/v1/search` endpoint.
- **Support Categories & Tags Filters**: Update the filter actions in `FolderDetailsView.tsx` (all/document/image/video and specific tags) to dynamically re-fetch files from `/api/v1/search` by mapping state to the request parameters.
- **Synchronize File Operations**: Integrate the Move To Folder and Delete operations inside the details view to invalidate and reload the files using React Query/API triggers.

## Capabilities

### New Capabilities
- `library/folder-contents-query`: Querying files of a specific folder dynamically via the `/api/v1/search` route.

### Modified Capabilities
<!-- None, we will set skip_specs: true in the .openspec.yaml of this change if needed, or simply write a delta spec for the folder query feature -->

## Impact

- `desktop/src/features/library/components/FolderDetailsView.tsx`: Core UI and listing logic.
- `desktop/src/features/library/hooks/useFolderFiles.ts`: A new hook to handle fetching of folder files.
- `desktop/src/services/api/search.ts`: Verify parameter types and API client.
