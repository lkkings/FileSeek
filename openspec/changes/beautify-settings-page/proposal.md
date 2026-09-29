## Why

The desktop settings page currently presents three equally weighted cards without a page-level hierarchy, and its visual treatment overuses gradients, glass effects, and unrelated radii. The page needs a calmer, more scannable product UI that makes language, tag, and storage settings feel like one coherent system.

## What Changes

- Add a settings page header that uses the existing `settings.title` and `settings.subtitle` translations.
- Reorganize the desktop layout so language settings occupy a compact sidebar column and tag management receives the primary column.
- Keep storage management as a wide section below the two-column area.
- Refine the settings visual system with global app tokens, consistent spacing, radii, borders, control heights, and state treatments.
- Improve visual hierarchy for tabs, tag chips, forms, empty states, errors, disabled controls, storage rows, and connection status.
- Preserve all existing settings behavior, API contracts, data mapping, localization, and accessibility semantics.

## Capabilities

### New Capabilities

- `settings/settings-page-ui`: User-facing presentation and layout requirements for the desktop settings page.

### Modified Capabilities

- None.

## Impact

- Affects the desktop settings feature components and their local CSS.
- May adjust the settings page wrapper CSS for the new page layout.
- Does not change backend APIs, settings data contracts, service calls, hooks, storage behavior, classifier labels, or persisted values.
- Does not add runtime dependencies or new third-party UI libraries.
