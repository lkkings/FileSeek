## Context

This design is focused entirely on the frontend implementation of folder layout updates and multi-select batch operations in FileSeek. See `proposal.md` for the motivation and overview.
The application is a TypeScript/React desktop client. Our work is confined to the frontend code with mock APIs.

## Goals / Non-Goals

**Goals:**
- Move "Edit" and "Delete" of folders to a custom "More Actions" dropdown list or simple context selector on each folder card in the `FolderSection`.
- Add "Import File" and "Import Folder" buttons in place of the old edit/delete action slots on folder cards.
- Format folder cards creation/modified time cleanly (e.g., standardizing `2026-09-20 14:32:00` or customized local formatting).
- Expose the number of files inside folder cards.
- Remove the discrete three-dots button from individual file cards in the folder details list.
- Support file card and search row item long-press (both touch/mousedown events) to enter batch select mode.
- Support selecting multiple items and performing batch "Delete (Move to Recycle Bin)" and "Move to Folder" actions.

**Non-Goals:**
- Actual backend or database modifications.
- Real file transport or OS-level file manipulation.

## Decisions

### 1. Folder Card Actions Dropdown
Instead of multiple standalone icon buttons on each folder card, we will use a custom dropdown menu.
- **Trigger**: Clicking the folder's "More" button displays a floating menu listing:
  1. *Edit Folder*
  2. *Delete Folder*
- **Positioning**: Absolute positioning below/near the card's relative button container.

### 2. Time Formatting and File Count
- Format folder record modified dates utilizing a helper to convert raw ISO strings or system timestamps to a standardized, reader-friendly layout like `YYYY-MM-DD HH:mm`.
- Since folder cards already carry a `fileCount` field (see `desktop/src/features/library/types.ts`), we will render this number as part of the card metadata.

### 3. Long Press Gesture Detection in React
To trigger multi-select mode, we'll design a standard custom React utility hook or mouse/touch event listeners.
- **Mechanism**:
  - `onMouseDown` and `onTouchStart` starts a timer of `600ms`.
  - `onMouseUp`, `onMouseLeave`, and `onTouchEnd` cancels the timer.
  - If the timer completes without cancellation, batch select mode is activated, and the current item is toggled as selected.
  - While batch select mode is active, simple clicks toggle item selection instead of opening the preview sidebar.

### 4. Batch Operations Floating Toolbar
When batch select mode is active (i.e., `selectedItems.size > 0`), a fixed or sticky bottom action bar appears.
- **Controls**:
  - "Delete Selected" (triggers deletion via hook with local state update, showing a success message).
  - "Move Selected" (displays a custom folder selection dropdown/modal to move files to another folder).
  - "Cancel" button to exit batch select mode and clear selections.

## Risks / Trade-offs

- **Risk**: Long-press colliding with drag-and-drop or normal tap gestures.
  - **Mitigation**: Setting the threshold to `600ms` and cancelling explicitly on any scroll/move/leave event.
- **Risk**: Event bubbling on action dropdowns within cards.
  - **Mitigation**: Stop event propagation using `e.stopPropagation()` and `e.preventDefault()`.
