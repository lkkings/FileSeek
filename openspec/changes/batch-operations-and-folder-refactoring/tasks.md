## 1. Folder Section Refactoring

- [x] 1.1 Refactor folder card actions in `FolderSection.tsx` to move Edit/Delete to a "More" dropdown, and verify menu triggers and item clicks work correctly.
- [x] 1.2 Replace Edit/Delete icons on cards with "Import File" and "Import Folder" icon buttons, and verify the buttons trigger the correct notification actions.
- [x] 1.3 Format folder modification time nicely on folder cards, and verify that dates display cleanly in localized format.
- [x] 1.4 Display the number of files inside each folder card (fileCount), and verify that it matches the badge and displays correctly.

## 2. Folder Details View Refactoring

- [x] 2.1 Remove the card-level discrete three-dots ("More actions") button from files in `FolderDetailsView.tsx`, and verify it is removed from the DOM.
- [x] 2.2 Add custom long-press gesture triggers to file cards in `FolderDetailsView.tsx` to enter batch operation mode, and verify that long pressing a card toggles its selection checkbox.
- [x] 2.3 Implement standard toggle clicks when batch selection is active, showing check-circle status overlays on selected cards, and verify checking/unchecking works properly.
- [x] 2.4 Add a persistent bottom bar for batch operations (Delete / Move) when one or more files are selected, and verify that the layout and options are visible.
- [x] 2.5 Hook up the mock batch "Delete" action to delete files from the local view array and trigger a notification, verifying the deleted files disappear from the view.
- [x] 2.6 Hook up the mock batch "Move" action to display a custom folder selector dropdown/menu, updating the file list/notification, and verify selection moves files locally.

## 3. Search Results View Refactoring

- [x] 3.1 Implement long press on rows in `SearchResultsView.tsx` to activate batch selection, and verify long pressing a search result triggers batch mode.
- [x] 3.2 Add check circles/boxes to search results in batch selection mode, and verify checkboxes reflect the selected state.
- [x] 3.3 Add the batch operations bottom bar in `SearchResultsView.tsx` with Delete and Move operations, and verify that delete/move actions function correctly and update the results view.
