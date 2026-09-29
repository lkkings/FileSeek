## Why

The Recycle page currently borrows the search-results layout and exposes preview/detail behavior even though the recycle bin does not need file previewing. This makes the page visually generic and leaves unnecessary preview state and component dependencies in a recovery-focused workflow.

## What Changes

- Give the Recycle page a dedicated visual hierarchy with a page header, summary, list, loading, error, empty, and pagination treatments.
- Keep existing recycle data loading, multi-select, long-press selection, restore, permanent-delete confirmation, pagination, notices, and error behavior.
- Remove the preview/detail drawer, file viewer overlay, selected-file mapping, preview callback, and per-row preview action from the Recycle page.
- Introduce narrowly scoped recycle page and row styles that follow the app's existing dark visual language and responsive behavior.

## Capabilities

### New Capabilities

- `recycle/bin`: Defines the user-visible presentation and preview-free interaction requirements for the desktop Recycle page.

### Modified Capabilities

- None.

## Impact

- Frontend only: `desktop/src/pages/recycle/RecyclePage.tsx`, `desktop/src/features/recycle/components/RecycleRowItem.tsx`, and recycle feature CSS.
- No backend, API contract, database schema, dependency, or data migration changes.
- The Recycle page no longer offers preview or detail entry points; existing recovery operations remain available.
