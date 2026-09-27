## Why

Users need a more efficient and stream-lined workflow for managing folders and files within the desktop client. Specifically, editing/deleting folders should be tucked away into a "More" menu to keep the main grid neat, and long-pressing files should activate a bulk actions bar to perform batch deletions and batch relocations directly.

## What Changes

- **Folder list view updates**:
  - Move "Edit" and "Delete" actions from the folder card's main row into the "More" dropdown.
  - Replace the original Edit/Delete slots with "Import File" and "Import Folder" buttons for immediate, intuitive file ingests.
  - Format the folder's modified date representation cleanly on the cards.
  - Expose the count of files contained inside each folder card.
- **Folder details page bulk actions**:
  - Remove individual more-actions icon buttons from file cards.
  - Introduce long-press triggering on file cards to activate batch operation mode.
  - Implement bulk selection check circles on file cards.
  - Render a persistent bottom bar during batch select mode for **Delete (Move to Recycle Bin)** and **Move to Folder** operations.
- **Search results page bulk actions**:
  - Implement long-press trigger for batch select mode on search row items.
  - Render the same persistent bulk actions bottom bar.

## Capabilities

### New Capabilities
None (Frontend UI only; no new specs)

### Modified Capabilities
None (Frontend UI only; no new specs)

## Impact

- `desktop/src/pages/library/LibraryPage.tsx`: Core page wiring for dialog states, notifications, and context passing.
- `desktop/src/features/library/components/FolderSection.tsx`: Layout updates for folder action icons and adding mock action-handlers for importing files/folders.
- `desktop/src/features/library/components/FolderDetailsView.tsx`: Touch/mouse long press gestures, multi-select active states, batch action bar.
- `desktop/src/features/file-search/components/SearchResultsView.tsx`: Multi-select, long press triggers, and batch actions bottom bar.
