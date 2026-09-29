## 1. Dialog Layout and Browsing States

- [x] 1.1 Refine the import dialog header, destination presentation, and storage tabs for clear hierarchy; verify the existing storage tab labels and keyboard switching remain unchanged.
- [x] 1.2 Reorganize the path toolbar and selection utilities with responsive wrapping; verify path navigation, select all, and invert selection still pass component tests.
- [x] 1.3 Improve file-row spacing, selected, hover, and focus states while preserving 44px minimum touch targets; verify directory clicks and persistent selections pass component tests.

## 2. Progress and Action Clarity

- [x] 2.1 Implement the progress summary and overall progress bar presentation; verify the existing progress percentages and totals render correctly in integration tests.
- [x] 2.2 Implement per-item state badges and readable error layout; verify queued, registered, processing, failed, and completed item states render without horizontal overflow.
- [x] 2.3 Refine the selected-count and dialog action footer; verify the start button remains disabled with no selections and starts the same import request after selection.

## 3. Validation

- [x] 3.1 Run the targeted import dialog tests in `desktop` and verify all existing behavior assertions pass.
- [x] 3.2 Run `npm run typecheck` and `npm run lint` in `desktop` and verify no new issues are introduced.
- [x] 3.3 Inspect the dialog at 760px and narrow responsive widths; verify browsing and progress states remain readable, scrollable, and accessible.
