## 1. Desktop Lifecycle

- [ ] 1.1 Add the required desktop dependencies, startup configuration, and tray state; verify the app builds and the tray icon renders on the development platform.
- [x] 1.2 Implement main-window close interception and tray restore/quit actions; verify unit tests cover hide, restore, quit, and non-main-window close decisions.
- [x] 1.3 Implement explicit silent-start argument handling so normal launches show the window and silent launches remain hidden; verify tests cover both startup modes and macOS activation-policy transitions.
- [x] 1.4 Implement tray backend availability polling using the existing connection file and health contract; verify tests cover connected, disconnected, and missing-connection states without starting or stopping the backend.
- [ ] 1.5 Add lifecycle regression coverage proving that closing and quitting never manage the external backend process; verify the lifecycle suite passes.

## 2. System Integration Settings

- [x] 2.1 Define typed desktop commands and state models for silent startup and file-manager integration; verify command serialization and default-off state tests pass.
- [ ] 2.2 Implement Windows current-user Run registration with the silent flag; verify tests cover create, read, update, remove, path mismatch, and quoted executable paths.
- [x] 2.3 Implement macOS LaunchAgent registration with program arguments and no keep-alive restart; verify generated plist and state tests pass.
- [x] 2.4 Implement Linux XDG autostart registration for supported desktop environments; verify generated desktop-entry and state tests pass.
- [x] 2.5 Add the settings integration card with independent toggles, loading, errors, and resulting-state feedback; verify component tests cover default off, enabling, disabling, and failed registration.
- [x] 2.6 Add i18n and accessibility labels for system integration settings; verify English and Chinese component snapshots or assertions pass.

## 3. System Import Bridge

- [x] 3.1 Implement startup-argument parsing for the add-files intent and normalize incoming paths; verify tests cover Windows, POSIX, multiple-file, duplicate, empty, directory, missing, and unreadable paths.
- [x] 3.2 Add single-instance handling that forwards add-file arguments to the resident instance and focuses its window; verify tests cover first launch, resident launch, and duplicate launches.
- [x] 3.3 Implement the frontend event and typed service bridge for system import requests; verify tests cover event payload validation, malformed events, and no token leakage.
- [x] 3.4 Implement storage-source mapping for received local and mounted paths; verify tests cover active local mapping, mounted-source mapping, no active source, and case or separator normalization.

## 4. Target Folder Import Flow

- [x] 4.1 Build the system import folder-selection dialog showing received files and available library folders; verify component tests cover loading, empty folders, selection, cancellation, and retry.
- [x] 4.2 Wire folder confirmation to the existing batch import hook and render existing SSE progress and per-file failures; verify integration tests cover successful import, item failure, and stream failure.
- [x] 4.3 Add invalid-path and unavailable-storage handling without creating import tasks; verify tests cover missing files, directories, unreadable files, and no active storage source.
- [x] 4.4 Add i18n, keyboard navigation, and dialog accessibility for the system import flow; verify component accessibility and language tests pass.

## 5. Platform File-Manager Integration

- [ ] 5.1 Implement the Windows Explorer first-level shell verb and multi-file command forwarding; verify registry generation/removal tests and manual Explorer validation on Windows 10 or 11.
- [ ] 5.2 Implement the macOS Finder Sync extension and selected-path forwarding; verify extension unit tests and manual Finder first-level menu validation.
- [ ] 5.3 Implement the GNOME Nautilus native first-level menu extension; verify extension tests and manual Files validation on a supported GNOME release.
- [ ] 5.4 Implement the KDE Dolphin first-level service menu; verify generated menu files and manual Dolphin validation on a supported KDE release.
- [ ] 5.5 Report macOS Finder extension approval status and provide the system-settings path when approval is missing; verify state tests and manual macOS approval flow.
- [ ] 5.6 Add packaging, signing, and install/uninstall cleanup for all native integrations; verify packaged artifacts include extensions and remove registrations when uninstalled.

## 6. Cross-Platform Validation

- [ ] 6.1 Run desktop Rust, TypeScript, lint, and frontend test suites; verify all targeted and regression tests pass.
- [ ] 6.2 Validate close-to-tray, silent startup, tray restore, and quit on Windows, macOS, GNOME, and KDE; verify the external backend remains unchanged in each case.
- [ ] 6.3 Validate first-level right-click import and multi-file forwarding in Explorer, Finder, Nautilus, and Dolphin; verify each platform reaches folder selection and batch import progress.
- [ ] 6.4 Validate integration toggles, default-off state, re-enable after app relocation, and uninstall cleanup on every supported platform; verify settings state always matches operating-system state.
