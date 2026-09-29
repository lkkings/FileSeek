## Why

FileSeek currently exits its desktop shell when the main window closes, and importing files requires opening the app before choosing a folder. Users need long-running indexing work to remain available in the background and need a native shortcut for adding files directly from the system file manager.

## What Changes

- Close the main window to the system tray instead of exiting the desktop application.
- Keep the externally managed backend process outside FileSeek's desktop lifecycle: closing or quitting FileSeek does not start or stop it.
- Add a tray entry for reopening the main window and deliberately quitting the desktop application.
- Support silent startup at login on Windows, macOS, and supported Linux desktop environments.
- Add a first-level file-manager context-menu action on Windows Explorer, macOS Finder, GNOME Files/Nautilus, and KDE Dolphin.
- Pass selected file paths into a target-folder selection flow and reuse the existing batch import and SSE progress contract.
- Add FileSeek settings controls for silent startup and file-manager integration, defaulting both to off.
- Constrain Linux support to common desktop environments and standard system-tray support; do not promise every Linux file manager.

## Capabilities

### New Capabilities

- `desktop/background-lifecycle`: Defines close-to-tray, tray restore and quit, silent startup, and the external-backend process boundary.
- `desktop/system-file-import`: Defines first-level file-manager integration, path forwarding, target-folder selection, and native import behavior.
- `settings/system-integration`: Defines the user-visible settings and state reporting for silent startup and file-manager integration.

### Modified Capabilities

- None.

## Impact

- Desktop Tauri lifecycle gains close interception, tray integration, single-instance handling, startup arguments, and platform integration registration.
- Desktop settings UI and typed frontend services gain a system-integration section and toggle state.
- Native platform integration is added for Windows Explorer, macOS Finder Sync, Nautilus, and Dolphin.
- The file import flow gains a system-initiated folder-selection entry while reusing the existing library batch import API and progress events.
- No backend API or external-backend process-management contract changes.
