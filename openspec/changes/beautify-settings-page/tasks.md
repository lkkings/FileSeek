## 1. Page Structure

- [x] 1.1 Add the localized settings page header and responsive layout wrappers to `SettingsPageView`; verify the existing `SettingsPage` tests still find all existing controls and regions.
- [x] 1.2 Keep language, tag, and storage sections in source order for keyboard and screen-reader navigation; verify the DOM order matches the order language, tags, storage.
- [x] 1.3 Add a settings-page test assertion for the localized page title and subtitle; verify `npm run test -- src/pages/settings/SettingsPage.test.tsx` passes.

## 2. Visual System

- [x] 2.1 Refactor settings-local visual tokens and card surfaces to use consistent global color, border, surface, spacing, and radius values; verify the page retains the dark app identity without overflowing its scroll container.
- [x] 2.2 Refine language controls, tag tabs, tag chips, forms, primary actions, secondary controls, and focus-visible treatments; verify all controls remain recognizable in default, hover, active, focus, and disabled states.
- [x] 2.3 Refine local and NAS storage rows, status badges, endpoint presentation, empty states, loading messages, and inline errors; verify long endpoints and empty groups remain readable without horizontal overflow.
- [x] 2.4 Implement the desktop two-column language/tag layout and the narrow single-column fallback; verify the layout at desktop and narrow viewport widths without introducing a second settings DOM tree.

## 3. Validation

- [x] 3.1 Run `npm run test -- src/pages/settings/SettingsPage.test.tsx` and resolve only regressions caused by this change.
- [x] 3.2 Run `npm run typecheck` and verify settings component changes remain type-safe.
- [x] 3.3 Run `npm run lint` and resolve only lint failures introduced by this change.
- [x] 3.4 Run `npm run build` and verify the desktop production build succeeds.
- [x] 3.5 Run `openspec validate beautify-settings-page --strict` and verify the change passes strict validation.
