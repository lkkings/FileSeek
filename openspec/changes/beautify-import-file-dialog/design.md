## Context

The import dialog already provides storage browsing, persistent multi-directory selection, batch start, and SSE-driven progress. Its React structure and styles live in `ImportFileDialog.tsx` and the feature-local `library.css`; the existing visual language is a dark blue product UI with one accent family.

## Goals / Non-Goals

**Goals:**

- Establish a clear reading order: destination and storage first, path and files second, selection and action last.
- Make selection and progress states visible without relying only on color.
- Keep the dialog comfortable at 760px desktop width and usable on narrower viewports.
- Preserve accessibility, i18n, keyboard behavior, and all import behavior.

**Non-Goals:**

- No changes to directory navigation, selection semantics, import requests, SSE transport, or task processing.
- No new component architecture, CSS methodology, design system, or third-party dependency.
- No landing-page-style hero treatment or decorative animation.

## Decisions

### Use a restrained workspace layout

Keep the modal's existing shell and dark blue palette, but separate the dialog into visually distinct header, navigation, list, and action regions. Use subtle surface boundaries, spacing, and typography rather than extra gradients. This preserves continuity with the rest of the library while reducing competition between controls.

### Keep changes in the existing component and stylesheet

Apply the refinement through existing class names and minimal JSX structure changes in `ImportFileDialog.tsx`, with styles in `library.css`. A new component or stylesheet would be unnecessary because the dialog remains one cohesive feature surface and the business model is unchanged.

### Prioritize the browsing action bar

Arrange the parent button, path input, and selection utilities so the path remains the dominant control. Allow the utility buttons to wrap on narrow widths instead of shrinking the path below a readable size. Keep buttons at or above existing minimum touch heights.

### Make file selection structural, not just colored

Use a visible checked state, row tint, and a subtle active edge for selected file rows. Preserve the current 44px minimum row height and label-based interaction so the whole row remains clickable.

### Treat progress as a summary-first view

Present overall total, success, failure, and percentage as a compact summary above the progress bar. Give each item a bounded status badge and let file names and errors truncate or wrap independently. This avoids the current fixed-column pressure where stage and error text can become unreadable.

### Preserve the single accent family

Use the existing blue accent for active navigation and the primary action, with limited success and failure semantic colors. Avoid introducing a second decorative accent. Ensure text and state indicators meet contrast expectations in the current dark theme.

## Risks / Trade-offs

- [Visual refinement could accidentally change behavior] -> Keep state, handlers, i18n keys, ARIA roles, and event flow unchanged; run the existing import dialog integration tests.
- [Taller rows and wrapped progress text could increase modal height] -> Keep bounded list scrolling, the current max dialog height, and responsive wrapping.
- [Additional visual states could reduce contrast] -> Use combinations of text, badge shape, and background, not color alone.

## Migration Plan

Update the component and feature-local CSS in one focused change. If the visual refinement needs rollback, revert those two files; no data, API, or persisted-state migration is involved.
