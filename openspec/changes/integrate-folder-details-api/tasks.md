## 1. API Service and Hook Creation

- [x] 1.1 Create `desktop/src/features/library/hooks/useFolderFiles.ts` which uses TanStack Query to call `/api/v1/search` with the folder ID. Verify typescript compiles without errors.

## 2. Views Refactoring

- [x] 2.1 Refactor `FolderDetailsView.tsx` to integrate with `useFolderFiles` instead of relying on hardcoded `INITIAL_FILES`. Verify dynamic category filtering works.
- [x] 2.2 Wire tag selection and filter logic inside the folder detail view to reload files by invalidating query keys. Verify typescript compiling succeeds.
- [x] 2.3 Wire folder actions (Delete, Move To Folder) within `FolderDetailsView.tsx` to trigger reloading of folder files. Verify correct reactivity.
