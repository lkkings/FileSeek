## Context

The folder details page currently combines a custom filter button, inline tag pills, a custom pagination footer, and table columns that do not adapt cleanly when the application sidebar expands or collapses. The project already has reusable `SearchBar`, `Pagination`, and `FileDetailDrawer` components, and the backend already models file tags, but it does not yet expose a dedicated tag-list endpoint.

## Goals / Non-Goals

**Goals:**

- Reuse the existing search bar, shared pagination, and file detail drawer.
- Keep folder-level filtering, sorting, paging, and preview behavior consistent with the rest of the library.
- Make the list layout respond to both viewport size and sidebar state.
- Provide a backend-backed tag selection surface.

**Non-Goals:**

- Do not redesign the overall library page or sidebar.
- Do not introduce a new state-management library or pagination implementation.
- Do not change file indexing or tag generation.

## Decisions

### Search toggle

Use a single icon button in the folder header as the only search-bar control. The button will keep two visual states: outline for inactive and filled for active. Reuse the existing `SearchBar` component and pass the current folder ID so searches stay scoped to the folder.

### Tag selection

Move tag chips into the same row as file-type filters, right-aligned after the category tabs. Add a compact “add tag” icon button that opens a popover. The popover will load tags from a new backend endpoint, for example `GET /api/v1/library/tags`, through a feature hook and API service. Selecting a tag will update the folder file query using the existing `tag` parameter.

This avoids deriving the full tag list from the current page, which would become incomplete as soon as pagination is used.

### Summary and sorting

Place the file count and sort control in one flex row. The count will occupy the left side and the sort control the right side. On narrow screens the row may wrap, but the sort control will remain visually grouped and right-aligned.

### Responsive list layout

Replace the current wide table with a responsive list layout built from repeated file rows. Each row will expose four logical fields: preview, tags, file name, and size. The layout will use the application sidebar state class plus viewport/container rules:

- Sidebar collapsed + small viewport: two columns.
- Sidebar expanded + small viewport: one column.
- Larger viewports: the four fields remain in one row.

This approach keeps the layout floating and avoids horizontal scrolling.

### Pagination

Reuse the existing shared `Pagination` component. The folder file query will continue to send `page_number` and `page_size`; the shared component will receive the current page, total count, and page-change callback.

### File interactions

Use a short single-click delay to distinguish single-click from double-click. Single click opens the existing `FileDetailDrawer`; double click opens the file preview directly. If the drawer is already open for the same file, a second single click will keep it open rather than toggling it closed.

## Risks / Trade-offs

- [Risk] A delayed single click may feel less instant. → Mitigation: keep the delay under 250 ms and open the preview immediately on double click.
- [Risk] The tag-list endpoint may be unavailable during rollout. → Mitigation: show an inline retry state and leave the current file list usable.
- [Risk] Sidebar state and viewport rules can drift. → Mitigation: centralize the responsive rules in the folder-details stylesheet and test the collapsed/expanded states explicitly.

## Migration Plan

1. Add the tag-list API and hook.
2. Update the folder details UI and interactions.
3. Replace custom pagination with the shared component.
4. Validate desktop and small-screen sidebar states.
5. Roll back by restoring the previous folder details component and pagination usage; the tag-list endpoint can remain backward-compatible.
