import AppKit
import FinderSync

final class FileSeekFinderSync: FIFinderSync {
    override func menu(for menuKind: FIMenuKind) -> NSMenu {
        let menu = NSMenu(title: "FileSeek")
        let item = NSMenuItem(
            title: "Add to FileSeek",
            action: #selector(addToFileSeek),
            keyEquivalent: ""
        )
        item.target = self
        menu.addItem(item)
        return menu
    }

    @objc private func addToFileSeek() {
        let selectedURLs = FIFinderSyncController.default().selectedItemURLs() ?? []
        guard !selectedURLs.isEmpty else { return }

        let applicationURL = Bundle.main.bundleURL
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .deletingLastPathComponent()
        let configuration = NSWorkspace.OpenConfiguration()
        configuration.arguments = ["--add"] + selectedURLs.map(\.path)
        NSWorkspace.shared.openApplication(
            at: applicationURL,
            configuration: configuration
        )
    }
}
