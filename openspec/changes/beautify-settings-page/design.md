## Context

The settings feature already owns the complete page content in `SettingsPageView` and its child components. The page wrapper only provides the scroll container, while the feature-local stylesheet owns nearly all visual styling. Existing i18n entries for the settings title and subtitle are available, so the header can be added without changing the translation catalog.

The desktop architecture requires feature-local UI, Lingui-backed labels, and no premature extraction of shared components. The existing settings API and state behavior are complete and must remain unchanged.

## Goals / Non-Goals

**Goals:**

- Establish page-level hierarchy and a responsive desktop-first layout.
- Create one settings-specific visual language for cards, controls, chips, rows, badges, and feedback states.
- Reuse global app color and focus tokens through semantic settings-local aliases.
- Preserve current DOM accessibility semantics, keyboard order, labels, and API behavior.

**Non-Goals:**

- No settings API, service, hook, persistence, or data-model changes.
- No new shared component library, global design-token system, or runtime dependency.
- No new settings functionality, navigation, or routing.
- No visual-regression framework or screenshot automation.

## Decisions

### Add the page header inside the settings feature

`SettingsPageView` will render the localized page header and the two-column layout wrapper. The page component will continue to own only layout and composition. This keeps the header with the feature content and avoids adding feature-specific copy or structure to `pages/settings`.

Alternative: render the header in the page wrapper. Rejected because the title, subtitle, and section layout all belong to the settings experience and the feature already owns the localized strings.

### Use a responsive grid rather than separate desktop and mobile trees

One DOM structure will contain the header, a top layout area, and the storage section. At desktop widths, the top area will use two columns with the language card as the compact column and tag management as the primary column. Below the selected breakpoint, the grid will collapse to one column and preserve source order.

Alternative: separate desktop and mobile markup. Rejected because duplicated content complicates localization and accessibility and can produce different keyboard or test-query results.

### Keep semantic CSS scoped to the settings feature

The settings stylesheet will define a small set of semantic aliases, such as surface, border, muted text, control, accent, and danger, and map them to the existing global app tokens where suitable. Component selectors will continue to use the existing settings naming style and remain under the settings feature.

Alternative: create a global card and form system. Rejected because only this page is being redesigned and the project rules discourage premature shared abstractions.

### Restrain the visual treatment

Cards will use calmer layered surfaces, consistent radii, and lighter borders and shadows. Primary actions will receive the strongest accent treatment, while secondary controls, chips, and status badges will remain quieter. Current icons may be used as decorative visual anchors, and interactive elements will keep their accessible names.

Alternative: apply the landing-page-style hero and heavy gradient language from the frontend design skill. Rejected because settings is a product UI where scanning, control recognition, and state clarity matter more than marketing impact.

### Preserve behavior and test contracts

Existing component names, callbacks, labels, and semantic regions will remain intact where tests rely on them. Layout-only wrappers and CSS classes may change. The existing settings page tests should continue to pass, with only targeted additions for the new page header if needed.

Alternative: rewrite the settings components around a new component architecture. Rejected because this is a presentation refinement, not a behavioral or structural refactor.

## Risks / Trade-offs

- [Risk] The two-column layout could overflow with long labels or storage endpoints. → Use `min-width: 0`, grid-friendly wrapping, and existing ellipsis behavior.
- [Risk] Reduced decoration could make the page feel less branded. → Retain the dark blue theme and accent identity through controlled surfaces, borders, and status color.
- [Risk] Layout wrappers could alter accessible or test-query relationships. → Keep interactive elements and semantic regions in source order and update only targeted tests if query assumptions change.
- [Risk] New state styling could be mistaken for new behavior. → Do not alter disabled predicates, loading conditions, or error messages; only their visual presentation.

## Migration Plan

1. Add the page header and responsive layout wrappers in the settings feature.
2. Refine the settings stylesheet in one pass so surface, control, status, and responsive rules remain internally consistent.
3. Update existing settings tests only where the page header is intentionally added.
4. Run the targeted settings test, then typecheck, lint, and production build.
5. Roll back is limited to the settings feature components and styles; no data or API migration is involved.
