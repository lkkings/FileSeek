## Context

`RecyclePage` currently renders the search-results screen and splits its layout to support a detail drawer. It maps recycle records into search file objects so the drawer can open previews. `RecycleRowItem` also renders a preview button and relies on search-result classes for core layout.

The page already has the required data hook, selection behavior, restore and permanent-delete mutations, pagination, confirmation dialog, and notices. The Tasks page demonstrates the app's current page-level visual language: local surface tokens, a rounded header, summary chips, and responsive toolbars.

## Goals / Non-Goals

**Goals:**

- Preserve all existing recycle recovery behavior and API contracts.
- Replace the search-page presentation with a dedicated, accessible recycle layout.
- Remove preview and detail state from the page and its row component.
- Keep styles narrowly scoped to the recycle feature and aligned with the existing desktop visual system.

**Non-Goals:**

- Adding per-row restore or delete actions.
- Changing recycle API requests, pagination behavior, query invalidation, or backend storage.
- Changing the shared FileDetailDrawer, FileViewerOverlay, or other pages that use preview.
- Introducing a new design system or CSS framework.

## Decisions

### Page composition

`RecyclePage` will own the page shell, header, summary, state rendering, pagination, and shared dialogs. `RecycleRowItem` will remain focused on rendering one recycle record and forwarding selection/long-press behavior.

This keeps the page as the composition boundary while avoiding a new wrapper component for a single page.

**Alternative considered:** extract a `RecycleListView`. This was rejected because it would add indirection without reuse; the page already has a small number of presentation branches.

### Preview removal

The page will no longer import or render `FileDetailDrawer`, `FileViewerOverlay`, `useFileViewer`, or `resolvePreviewCategory`. It will remove selected-file mapping and sidebar state. The row component will remove its `onOpenDetails` prop, preview button, and preview-focused styles.

Row click and long-press will continue to toggle selection. This is the intended recovery workflow and matches the no-preview requirement.

### Visual structure

The page will use dedicated `recycle-page` classes and local CSS custom properties derived from global app colors. It will render:

- A rounded header with a trash icon, title, subtitle, and compact total/selected summary.
- A content surface containing loading, error, empty, list, and pagination states.
- Rows with a file-type badge, name, path, deletion time, and size.
- Recycle-specific empty, error, and loading treatments.

The layout will follow the Tasks page's hierarchy and spacing rather than adding a new visual direction. The shared `BatchOperationsBar`, `DeleteConfirmDialog`, `Notice`, and `Pagination` components remain unchanged.

**Alternative considered:** continue styling on top of `search-results.css`. This was rejected because it would preserve search-specific semantics and make responsive adjustments harder to reason about.

### Stylesheet ownership

The extended recycle feature stylesheet will contain page and row styles and use global design tokens where possible. `RecyclePage` will import it instead of the search-results stylesheet. `RecycleRowItem` will no longer import the search-results stylesheet.

CSS will use no JavaScript-in-CSS or runtime styling dependency. Existing media-query breakpoints will be retained where they match the page's behavior, with a compact layout below 781px and a stacked row layout below 481px.

### Accessibility

Interactive elements will keep semantic buttons, `aria-label`s, `aria-pressed` state, and visible `:focus-visible` outlines. The list region will remain announced with `aria-live="polite"` only when data state changes. Text will wrap or truncate with ellipsis while preserving the primary file name and path.

## Risks / Trade-offs

- [Removing the only explicit right-side row action may reduce discoverability of selection] → Row click and long-press remain primary affordances, while the shared batch bar appears as soon as an item is selected.
- [A dedicated layout could drift from the rest of the desktop app] → Reuse global color variables, spacing scale, radii, and the Tasks page's established hierarchy.
- [Removing search-result CSS dependencies may expose hidden row styling assumptions] → Replace the required row, selection, icon, metadata, and responsive rules explicitly in the recycle stylesheet and inspect all required viewport widths.
- [Small viewport layouts can clip long paths] → Use min-width constraints, text truncation, and metadata wrapping in the recycle row rules.

## Migration Plan

1. Remove the preview/detail imports, state, mapping, handlers, and row callback from `RecyclePage`.
2. Introduce dedicated page shell, header, summary, state, list, and pagination markup.
3. Update `RecycleRowItem` props and markup for preview-free selection behavior.
4. Replace search-result CSS dependencies with scoped recycle page and row styles.
5. Add or update focused frontend tests for preview removal, selection, and core recovery operations.
6. Run typecheck, lint, tests, and visual inspection at desktop and responsive widths.

Rollback is limited to the Recycle page, row component, recycle stylesheet, and focused tests. No backend, API, schema, or shared component changes are required.
