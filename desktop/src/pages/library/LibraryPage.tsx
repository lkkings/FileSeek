import { useMemo, useState } from "react";
import { AdvancedFilters, SearchBar, useFileSearch } from "../../features/file-search";
import { SearchResultsView } from "../../features/file-search/components/SearchResultsView";
import { FileViewerOverlay, useFileViewer } from "../../features/file-preview";
import {
  FolderSection,
  FolderDialog,
  DeleteFolderDialog,
  ImportFileDialog,
  SystemImportDialog,
  useFileLibrary,
  useSystemImportRequest,
  FolderDetailsView,
  useBatchImport,
  useMoveFilesToFolder,
} from "../../features/library";
import { useSettingsPreferences } from "../../features/settings";
import { useMoveFilesToRecycle } from "../../features/recycle";
import { useRecordRecentAccess } from "../../features/recent";
import type { FolderRecord, FolderFormValues } from "../../features/library";
import { mapSystemImportPaths } from "../../features/library/services/systemImportMapping";
import { Notice } from "../../components/Notice";
import { useTranslate } from "../../i18n/useTranslate";
import { errorText } from "../../services/api/client";
import type { FileItem } from "../../services/api/search";
import "./library-page.css";

export function LibraryPage() {
  const t = useTranslate();
  const [notice, setNotice] = useState("");
  const { filters, updateFilter, resetFilters, searchState, submitSearch, changePage, changeSorting } = useFileSearch();
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const [currentFolder, setCurrentFolder] = useState<FolderRecord | null>(null);
  const [showFolderSearch, setShowFolderSearch] = useState(false);
  const moveFilesToRecycle = useMoveFilesToRecycle();
  const moveFilesToFolder = useMoveFilesToFolder();
  const recordRecentAccess = useRecordRecentAccess();
  const fileViewer = useFileViewer();
  const { preferences } = useSettingsPreferences();

  // Folder library hooks and state
  const {
    folders,
    loading: libraryLoading,
    error: libraryError,
    reload: reloadLibrary,
    createFolder,
    updateFolder,
    deleteFolder,
  } = useFileLibrary();

  const [activeDialog, setActiveDialog] = useState<"create" | "edit" | "delete" | "import" | null>(null);
  const [selectedFolder, setSelectedFolder] = useState<FolderRecord | undefined>(undefined);
  const batchImport = useBatchImport(selectedFolder?.id ?? "", setNotice);
  const systemImportBatch = useBatchImport("", setNotice);
  const [dialogSubmitting, setDialogSubmitting] = useState(false);
  const [dialogError, setDialogError] = useState<string | null>(null);
  const [systemImportRequest, setSystemImportRequest] = useState<{
    paths: string[];
    errors: string[];
  } | null>(null);
  useSystemImportRequest(setSystemImportRequest);
  const systemImportMapping = useMemo(
    () =>
      systemImportRequest
        ? mapSystemImportPaths(systemImportRequest.paths, preferences.storageDrives)
        : null,
    [preferences.storageDrives, systemImportRequest],
  );

  function handleResetFilters() {
    resetFilters();
    setNotice(t("search.resetNotice", "筛选条件已重置"));
  }

  function handleSearch() {
    submitSearch({ folderId: currentFolder ? currentFolder.id : null }).then((res) => {
      if (res.ok) {
        setNotice(`${t("search.found", "找到")} ${res.resultCount} ${t("search.results", "条结果")}`);
      }
      setIsSearching(true);
    });
  }

  function handleReturnToLibrary() {
    setIsSearching(false);
    setShowFolderSearch(false);
    resetFilters();
  }

  const handleMoveToRecycle = async (fileIds: string[]) => {
    const response = await moveFilesToRecycle.mutateAsync(fileIds);
    return response.status === "success";
  };

  const handleMoveToFolder = async (fileIds: string[], targetFolderId: string) => {
    const response = await moveFilesToFolder.mutateAsync({ fileIds, targetFolderId });
    return response.status === "success";
  };

  const handleOpenFile = async (file: FileItem) => {
    fileViewer.openFile({
      fileId: file.file_id,
      fileName: file.file_name,
      fileType: file.category as "document" | "image" | "video",
      ...(typeof file.metadata?.page_number === "number" && file.metadata.page_number > 0
        ? { initialPageNumber: file.metadata.page_number }
        : {}),
      ...(typeof file.metadata?.start_time === "number" && Number.isFinite(file.metadata.start_time)
        ? { startTime: file.metadata.start_time }
        : {}),
    });

    const response = await recordRecentAccess.mutateAsync(file.file_id);
    if (response.status !== "success") {
      const failedNotice = errorText(response.error) || t("recent.recordFailed", "记录访问失败");
      setNotice(failedNotice);
    } else {
      const accessNotice = `${t("recent.recorded", "已记录访问")} “${file.file_name}”`;
      setNotice(accessNotice);
    }
  };

  const refreshSearch = () => {
    void submitSearch({ folderId: currentFolder ? currentFolder.id : null });
  };

  const handleSortByChange = (sortBy: "relevance" | "created_at" | "size") => {
    void changeSorting(sortBy, searchState.sortOrder);
  };

  const handleSortOrderChange = (sortOrder: "asc" | "desc") => {
    void changeSorting(searchState.sortBy, sortOrder);
  };

  const handlePageChange = (pageNumber: number) => {
    void changePage(pageNumber);
  };

  async function handleCreateSubmit(values: FolderFormValues) {
    setDialogSubmitting(true);
    setDialogError(null);
    const err = await createFolder(values);
    setDialogSubmitting(false);
    if (err) {
      setDialogError(err);
    } else {
      setActiveDialog(null);
      setNotice(t("folder.created", "文件夹已创建"));
    }
  }

  const handleSystemImportConfirm = async (folderId: string) => {
    if (!systemImportMapping || systemImportMapping.selections.length === 0) {
      return false;
    }
    return systemImportBatch.start(systemImportMapping.selections, folderId);
  };

  async function handleEditSubmit(values: FolderFormValues) {
    if (!selectedFolder) return;
    setDialogSubmitting(true);
    setDialogError(null);
    const err = await updateFolder(selectedFolder.id, values);
    setDialogSubmitting(false);
    if (err) {
      setDialogError(err);
    } else {
      setActiveDialog(null);
      setNotice(t("folder.updated", "文件夹已更新"));
    }
  }

  async function handleDeleteConfirm() {
    if (!selectedFolder) return;
    setDialogSubmitting(true);
    setDialogError(null);
    const err = await deleteFolder(selectedFolder.id);
    setDialogSubmitting(false);
    if (err) {
      setDialogError(err);
    } else {
      setActiveDialog(null);
      setNotice(t("folder.deleted", "文件夹已删除"));
    }
  }

  return (
    <>
      <main className={`main-content ${advancedOpen ? "" : "filters-collapsed"}`}>
        <section className="search-results-screen" aria-label={t("search.resultsLabel", "搜索结果")}>
          {(isSearching || !currentFolder || showFolderSearch) && (
            <>
              <SearchBar
                query={filters.globalQuery}
                onQueryChange={(value) => updateFilter("globalQuery", value)}
                onClear={() => updateFilter("globalQuery", "")}
                onSubmit={handleSearch}
                advancedOpen={advancedOpen}
                onOpenAdvanced={() => setAdvancedOpen((current) => !current)}
              />
              {advancedOpen && <AdvancedFilters filters={filters} onUpdate={updateFilter} onReset={handleResetFilters} />}
            </>
          )}
          
          {isSearching ? (
            <SearchResultsView
              query={filters.globalQuery}
              onNotice={setNotice}
              onMoveToRecycle={handleMoveToRecycle}
              onMoveToFolder={handleMoveToFolder}
              folders={folders}
              foldersLoading={libraryLoading}
              foldersError={libraryError}
              searchScopeFolderId={currentFolder ? currentFolder.id : null}
              onOpenFile={handleOpenFile}
              onRefresh={refreshSearch}
              onPageChange={handlePageChange}
              currentPage={searchState.pageNumber}
              pageSize={searchState.pageSize}
              totalItems={searchState.resultCount}
              sortBy={searchState.sortBy}
              sortOrder={searchState.sortOrder}
              onSortByChange={handleSortByChange}
              onSortOrderChange={handleSortOrderChange}
              data={searchState.data ?? undefined}
              status={searchState.status}
              error={searchState.error}
              onBack={handleReturnToLibrary}
            />
          ) : currentFolder ? (
            <FolderDetailsView
              folder={currentFolder}
              onBack={() => { setCurrentFolder(null); setShowFolderSearch(false); }}
              onFolderAction={(msg) => setNotice(message => message ? message + "\n" + msg : msg)}
              onToggleSearch={() => setShowFolderSearch((prev) => !prev)}
              isSearchActive={showFolderSearch}
              folders={folders}
              onMoveToRecycle={handleMoveToRecycle}
              onMoveToFolder={handleMoveToFolder}
              onOpenFile={handleOpenFile}
            />
          ) : (
            <FolderSection
              folders={folders}
              loading={libraryLoading}
              error={libraryError}
              onCreateFolder={() => {
                setSelectedFolder(undefined);
                setDialogError(null);
                setActiveDialog("create");
              }}
              onEditFolder={(folder) => {
                setSelectedFolder(folder);
                setDialogError(null);
                setActiveDialog("edit");
              }}
              onRequestDeleteFolder={(folder) => {
                setSelectedFolder(folder);
                setDialogError(null);
                setActiveDialog("delete");
              }}
              onImportFiles={(folder) => {
                setSelectedFolder(folder);
                setDialogError(null);
                setActiveDialog("import");
              }}
              onRetry={reloadLibrary}
              onEnterFolder={(folder) => { setCurrentFolder(folder); setShowFolderSearch(false); }}
            />
          )}
        </section>
      </main>

      {notice && <Notice message={notice} onClose={() => setNotice("")} />}

      {activeDialog === "create" && (
        <FolderDialog
          mode="create"
          submitting={dialogSubmitting}
          error={dialogError}
          onClose={() => setActiveDialog(null)}
          onSubmit={handleCreateSubmit}
        />
      )}

      {activeDialog === "edit" && selectedFolder && (
        <FolderDialog
          mode="edit"
          folder={selectedFolder}
          submitting={dialogSubmitting}
          error={dialogError}
          onClose={() => setActiveDialog(null)}
          onSubmit={handleEditSubmit}
        />
      )}

      {activeDialog === "delete" && selectedFolder && (
        <DeleteFolderDialog
          folder={selectedFolder}
          submitting={dialogSubmitting}
          error={dialogError}
          onClose={() => setActiveDialog(null)}
          onConfirm={handleDeleteConfirm}
        />
      )}

      {activeDialog === "import" && selectedFolder && (
        <ImportFileDialog
          folderName={selectedFolder.name}
          storageLocations={preferences.storageDrives}
          importState={batchImport.state}
          onStart={batchImport.start}
          onClose={() => setActiveDialog(null)}
        />
      )}

      {systemImportRequest && systemImportMapping && (
        <SystemImportDialog
          requestPaths={systemImportRequest.paths}
          requestErrors={systemImportRequest.errors}
          selections={systemImportMapping.selections}
          invalidPaths={systemImportMapping.invalidPaths}
          unmappedPaths={systemImportMapping.unmappedPaths}
          storageRequired={systemImportMapping.storageRequired}
          folders={folders}
          foldersLoading={libraryLoading}
          foldersError={libraryError}
          importState={systemImportBatch.state}
          onConfirm={handleSystemImportConfirm}
          onRetry={() => void reloadLibrary()}
          onClose={() => setSystemImportRequest(null)}
        />
      )}

      <FileViewerOverlay
        isOpen={fileViewer.isOpen}
        item={fileViewer.item}
        onClose={fileViewer.onClose}
      />
    </>
  );
}
