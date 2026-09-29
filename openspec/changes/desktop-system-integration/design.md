## Context

The current Tauri shell has no tray, close interception, single-instance handling, or operating-system integration. The library already provides folder listing, batch import, and SSE progress. The backend is externally managed and publishes its connection through a local connection file, so the desktop shell must not treat backend process ownership as part of its lifecycle.

Historical repository work contains a useful cross-platform login-registration design, but it was removed and predates the current preview and import transport structure. It should be used as reference only.

## Goals / Non-Goals

**Goals:**

- Keep the desktop shell resident with a clear close, restore, and quit lifecycle.
- Support silent login startup on Windows, macOS, and common Linux desktop environments.
- Provide first-level file-manager actions on Windows Explorer, macOS Finder, GNOME Files/Nautilus, and KDE Dolphin.
- Route system-selected files into a folder-selection UI and the existing import contract.
- Keep integration state truthful by reading operating-system registration or extension state.

**Non-Goals:**

- Starting, monitoring, restarting, or stopping the external backend process.
- Supporting every Linux desktop environment or file manager.
- Implementing Finder actions through a Services submenu or Nautilus Scripts submenu.
- Changing backend import APIs, folder APIs, or task progress semantics.
- Copying or moving source files during import.

## Decisions

### Keep backend ownership external

The desktop shell will only read the existing backend connection and display availability. Closing or quitting FileSeek will never manage the backend process.

Alternative considered: restore the historical backend sidecar. This was rejected because the requirement explicitly assumes an already-running external backend.

### Intercept close and expose tray controls

The main window close request will be prevented and the window hidden. A tray menu will expose open and quit actions. Quit will exit only the Tauri process.

Alternative considered: allow the final window close to exit the app and rely on login startup. This would break background import access and violate the close-to-tray requirement.

### Use an explicit silent-start argument

Normal launches will show the main window. Login registrations will invoke the executable with a silent flag; the shell will keep the initial window hidden and show only the tray. macOS will use an accessory activation policy while hidden and become regular when the main window is shown.

Alternative considered: infer silent mode from login registration. An explicit argument keeps manual launches predictable and makes startup behavior testable.

### Register startup per platform

- Windows: current-user Run registry value.
- macOS: LaunchAgent plist with program arguments.
- Linux: XDG autostart desktop entry.

The registration will include the silent flag and point to the current executable. The settings state will be read back from the platform registration rather than trusted from a local UI value.

### Forward paths through one desktop instance

A single-instance layer will receive launch arguments, detect the add-files intent, focus the existing window, and emit a typed frontend event with normalized file paths. If the app is not running, the context action will start it with the same arguments and then show the import flow.

Alternative considered: launch a fresh window for every context invocation. This risks duplicate processes and conflicts with close-to-tray behavior.

### Use native first-level menu integrations

- Windows Explorer: current-user shell verb configured for multi-file selection.
- macOS Finder: Finder Sync extension that passes selected paths to FileSeek.
- GNOME Files/Nautilus: native Nautilus menu extension.
- KDE Dolphin: service menu entry.

Services and Nautilus scripts were rejected because they appear in submenus rather than the required first level.

macOS Finder Sync is subject to system extension approval. FileSeek will report the actual Finder extension state and guide users to macOS system settings when approval is required.

### Reuse the existing import flow

The system import event will open a destination-folder dialog that lists existing folders and received files. Confirming the dialog will use the existing batch import request and SSE progress consumer.

Path validation will normalize paths, reject directories and unreadable files, and map each path to the active local storage source, or to a matching mounted source when applicable.

Alternative considered: add a backend endpoint dedicated to system imports. This duplicates the existing batch contract without changing observable import behavior.

### Model integration state in desktop commands

Typed Tauri commands will expose and update operating-system integration state. The settings page will call those commands and show platform-specific status, including the macOS extension-approval state.

Alternative considered: persist only a frontend preference. This can disagree with the operating system after app moves, upgrades, or manual system changes.

## Risks / Trade-offs

- [macOS Finder Sync is complex] -> Bundle the extension with the app, keep path forwarding simple, and report system approval state honestly.
- [Linux menu and tray support varies] -> Limit the supported matrix to Windows, macOS, GNOME Files/Nautilus, and KDE Dolphin with standard system-tray support.
- [Multi-select behavior differs by file manager] -> Validate selected-path forwarding separately on each supported platform.
- [External backend may be unavailable] -> Show backend disconnected state in the tray and reuse existing frontend errors when the window opens.
- [App path changes can invalidate registrations] -> Read actual system state and let users re-enable integration; avoid claiming an integration the operating system no longer holds.

## Migration Plan

1. Add lifecycle behavior while leaving external backend management unchanged.
2. Add settings controls and platform registration behind default-off switches.
3. Add path forwarding and destination-folder selection.
4. Add each platform's first-level file-manager integration.
5. Validate the supported platform matrix before release.

Rollback consists of disabling the two operating-system integrations and reverting the desktop shell changes; no backend data migration is required.
