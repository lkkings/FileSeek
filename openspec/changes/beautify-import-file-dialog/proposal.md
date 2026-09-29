## Why

The import dialog is functionally complete, but its storage tabs, path toolbar, file list, progress summary, and actions compete for attention at the same visual level. Users need a calmer, more scannable import workspace that makes the current destination, selected files, primary action, and per-item progress obvious.

## What Changes

- Refine the import dialog around a single deep-blue product accent and a restrained "file navigation workspace" visual language.
- Improve the visual hierarchy of the header, destination, storage tabs, path navigation, file list, selection count, and dialog actions.
- Give file rows clearer selected, hover, and focus states while preserving their existing touch targets.
- Redesign the progress view as a summary layer, overall progress bar, and per-item status list with readable state and error presentation.
- Improve responsive layout for the path toolbar and actions without changing navigation or selection behavior.
- Keep all existing i18n labels, ARIA semantics, keyboard behavior, import logic, SSE handling, and API contracts unchanged.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- None. This is a presentation-only refinement and does not alter any existing requirement.

## Impact

- `desktop/src/features/library/components/ImportFileDialog.tsx`
- `desktop/src/features/library/components/library.css`
- Existing import dialog component tests should continue to pass without behavior-focused changes.
