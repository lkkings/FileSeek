## 1. Preview Removal

- [x] 1.1 Remove preview/detail imports, selected-item state, selected-file mapping, viewer handlers, drawer markup, and overlay markup from `RecyclePage` and verify the focused page test finds no preview or detail entry points
- [x] 1.2 Remove `onOpenDetails`, the preview button, and preview-only CSS from `RecycleRowItem` and verify the focused row test confirms clicking a row only toggles selection

## 2. Recycle Page UI

- [x] 2.1 Implement the dedicated recycle page shell, header, subtitle, total/selected summary, content surface, and state regions in `RecyclePage` and verify page tests cover populated, empty, loading, and error states
- [x] 2.2 Preserve multi-select, select all, invert selection, long-press, restore, confirmed permanent deletion, pagination, and notices and verify the existing focused page tests continue to pass

## 3. Row And Responsive Styling

- [ ] 3.1 Replace the row's search-result class dependencies with recycle-specific row, type icon, metadata, selection, and focus styles and verify visual inspection shows readable rows at desktop width
- [ ] 3.2 Add scoped responsive rules for the recycle page, summary, rows, pagination, and batch bar and verify visual inspection at 1024px, 780px, and 480px widths
- [ ] 3.3 Replace the page's search-results stylesheet import with the recycle feature stylesheet and verify no recycle component imports `search-results.css`

## 4. Tests And Validation

- [ ] 4.1 Update `RecyclePage.test.tsx` and `RecycleRowItem.test.tsx` to cover preview removal, dedicated page states, selection, restore, and permanent deletion and verify the focused Vitest suite passes
- [ ] 4.2 Run the desktop typecheck, lint, and test commands and verify all required checks pass
- [ ] 4.3 Start the desktop frontend, exercise the populated and empty recycle-bin states with the backend or test transport, and verify page interactions, notices, pagination, and responsive layouts match the specification
