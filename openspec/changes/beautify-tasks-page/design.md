## Context

The Tasks page is a product-style monitoring surface rather than a marketing page. It currently reuses the search result layout and feature-local task styles, with functional status filters, task rows, pagination, and a detail drawer. The existing React architecture requires feature-local UI, Lingui-backed copy, and no behavior changes for this presentation refinement.

See `proposal.md` for motivation and `specs/tasks/task-page-ui/spec.md` for observable requirements.

## Goals / Non-Goals

**Goals:**

- Establish a clear page hierarchy and calm visual rhythm for the Tasks queue.
- Make task state, progress, and recovery actions easier to scan.
- Refine loading, empty, and error states while preserving current behavior.
- Keep styles feature-local and aligned with the existing dark theme and global tokens.

**Non-Goals:**

- No task API, service, hook, polling, mutation, or data-model changes.
- No new task functionality, navigation, or drawer behavior.
- No new dependency or global design-token system.
- No marketing-page hero treatment.

## Decisions

### Keep task UI feature-local

Task-specific page and row styling will remain in the tasks feature stylesheet. The page component will continue to compose feature UI and own page-local state. This follows the existing architecture and avoids premature shared components.

Alternative: extract a shared dashboard card system. Rejected because the current change is scoped to Tasks and the project discourages premature abstraction.

### Use a restrained product UI language

The redesign will use quieter surfaces, consistent radii, semantic status color, and limited motion. Hierarchy will come from spacing, typography, and status emphasis rather than heavy gradients or decorative effects.

Alternative: apply landing-page visual treatments from the design skill. Rejected because Tasks is a data-dense monitoring surface where clarity and control recognition matter more than cinematic impact.

### Preserve behavior and semantics

Existing task statuses, filter options, retry and remove predicates, pagination, drawer behavior, and user-visible text semantics will remain unchanged. CSS classes and layout-only wrappers may change, but interactive elements will keep accessible names and source order.

Alternative: rebuild the page around new components and interactions. Rejected because this is a visual refinement and existing tests encode important behavior contracts.

### Reuse existing responsive breakpoints

The design will preserve the current desktop, compact sidebar-expanded, and mobile row behavior. Where layout pressure exists, the implementation will reduce secondary detail before removing required state information.

Alternative: introduce a new breakpoint system. Rejected because it would expand scope and risk regressions in unrelated layouts.

## Risks / Trade-offs

- [Risk] Reduced decoration could make the page feel less branded] -> Retain the established dark blue identity through controlled surface layers, accent borders, and status color.
- [Risk] Denser task rows could overflow with long paths and error text] -> Use `min-width: 0`, wrapping where appropriate, and ellipsis for secondary text.
- [Risk] Visual wrappers could change accessibility or test relationships] -> Preserve interactive semantics and update only targeted test assertions if layout structure changes.
- [Risk] Motion could distract during polling updates] -> Use short transitions and respect the existing reduced-motion global rule.

## Migration Plan

1. Refine the Tasks page header, toolbar, and summary structure.
2. Refine task row hierarchy, progress, stage, status, and action styling.
3. Refine loading, empty, and error states.
4. Update focused tests only where structure or query assumptions change.
5. Run the Tasks page test, typecheck, lint, and production build.
6. Roll back is limited to the Tasks page, task row component, task stylesheet, and focused tests.
