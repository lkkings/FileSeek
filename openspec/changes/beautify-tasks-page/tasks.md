## 1. Page Structure

- [ ] 1.1 Refactor the Tasks page header and status summary hierarchy, and verify the page title, total, processing, and failed counts remain visible in the Tasks page test.
- [ ] 1.2 Refine the status filter and retry-all toolbar layout, and verify all status filters and the retry-all disabled state remain accessible by role.
- [ ] 1.3 Update feature-local task styles with consistent surface, border, radius, spacing, and control tokens, and verify no new shared component or dependency is introduced.

## 2. Task Row Presentation

- [ ] 2.1 Refine the TaskRowItem layout for file identity, status, progress, stage, and error hierarchy, and verify the existing Task.pdf row and action labels still render.
- [ ] 2.2 Refine status, progress, and stage visual treatments for queued, processing, completed, and failed tasks, and verify the existing status labels remain unchanged.
- [ ] 2.3 Preserve compact and mobile responsive behavior, and verify task rows do not require horizontal scrolling at the existing breakpoints.

## 3. State Feedback

- [ ] 3.1 Refine the task loading skeleton and verify the loading state remains non-blocking and semantically labeled.
- [ ] 3.2 Refine the filtered empty state and verify the existing localized title and hint remain visible.
- [ ] 3.3 Refine the task list error state and verify the user-facing error text remains visible.

## 4. Validation

- [ ] 4.1 Update focused Tasks page tests only for intentional structure changes, and verify `npm run test -- TasksPage` passes.
- [ ] 4.2 Run typecheck, lint, and production build, and verify all pass with no new warnings related to the Tasks page.
- [ ] 4.3 Visually inspect the Tasks page in desktop, compact sidebar-expanded, and mobile layouts, and verify task state, progress, and actions remain clear.
