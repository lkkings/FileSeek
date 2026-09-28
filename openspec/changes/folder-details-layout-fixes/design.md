## Context

The folder details page currently uses an icon that reads as a dropdown for breadcrumb navigation, places tag selection beside file type filters, duplicates the file total above the list, and aligns pagination and list columns inconsistently. The page already has a shared `Pagination` component and feature-local list/grid components, so the changes are layout and interaction-only.

## Goals / Non-Goals

**Goals:**

- Make the back action visually and semantically obvious.
- Keep file type filters and tag filters on separate rows.
- Reduce duplicate pagination metadata.
- Keep list-view columns stable and readable across sidebar states.

**Non-Goals:**

- Do not change the file data model, search request, or tag data source.
- Do not redesign the folder library page or global sidebar.
- Do not introduce a new pagination implementation.

## Decisions

### Back button

Use a compact back button with a left-pointing chevron beside the breadcrumb. The button will call the existing `onBack` callback and will not open any menu.

### Tag filter row

Move the tag chips to a dedicated row directly under the category filter row. The row will use `overflow-x: auto`, `flex-wrap: nowrap`, and hidden scrollbars to keep every tag on one line. This avoids a popover and keeps all available filters visible without occupying header space.

### File total and pagination

Remove the “共 * 个文件” row and rely on the shared pagination component. Update the pagination footer to a three-region layout: left spacer, centered controls, and right-aligned total statistic. This keeps the page controls centered while making the total unambiguous.

### List view columns

Reorder the logical columns to “预览、文件名、标签、大小”. Center header labels and keep the responsive column widths from the existing sidebar-aware stylesheet. This fixes the current mismatch between visual order and semantic order.

## Risks / Trade-offs

- [Risk] Hidden scrollbars may make overflow less obvious. → Mitigation: add subtle edge fading and allow wheel/drag scrolling.
- [Risk] Centering pagination controls while right-aligning totals can crowd small screens. → Mitigation: collapse to a stacked layout only under 640px.
- [Risk] Changing column order may affect existing tests. → Mitigation: update component tests to assert the new order and centered headers.

## Migration Plan

1. Update folder details navigation and tag-row markup.
2. Remove the duplicate total and adjust pagination layout.
3. Reorder and center list-view columns.
4. Update component and layout tests.
5. Roll back by restoring the prior markup and stylesheet rules.
