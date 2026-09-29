## Why

The desktop Tasks page presents useful queue information, but its current hierarchy is visually crowded and its loading, empty, and row states do not provide enough scanning clarity. As a product-style monitoring surface, it needs a calmer and more readable treatment that keeps state and progress unmistakable.

## What Changes

- Add a clearer Tasks page header with a title, concise page context, and status summary.
- Refine the status filter group and retry action so primary controls are easier to distinguish.
- Improve task row hierarchy for file information, status, progress, stage flow, and errors.
- Upgrade loading skeletons, empty states, and error presentation without changing their behavior.
- Align spacing, radii, borders, status colors, hover states, and focus states with the existing dark desktop visual system.
- Preserve the current task API contract, filtering, pagination, retry behavior, removal behavior, drawer behavior, i18n, accessibility semantics, and responsive breakpoints.

## Capabilities

### New Capabilities

- `tasks/task-page-ui`: User-facing presentation and interaction requirements for the desktop Tasks page.

### Modified Capabilities

- None.

## Impact

- Affects `desktop/src/pages/tasks/TasksPage.tsx`.
- Affects `desktop/src/features/tasks/components/TaskRowItem.tsx`.
- Affects `desktop/src/features/tasks/components/tasks.css`.
- May adjust focused Tasks page tests if visual structure changes test-query assumptions.
- Does not change backend APIs, data contracts, task behavior, polling, dependencies, or persistence.
