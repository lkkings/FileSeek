import { useState } from "react";
import { AdvancedFilters, SearchBar, useFileSearch } from "../../features/file-search";
import { useFileActions } from "../../features/file-search/hooks/useFileActions";
import { SearchResultsView } from "../../features/file-search/components/SearchResultsView";
import {
  FolderSection,
  FolderDialog,
  DeleteFolderDialog,
  useFileLibrary,
  FolderDetailsView,
} from "../../features/library";
import { useMoveFilesToRecycle } from "../../features/recycle";
import { useRecordRecentAccess } from "../../features/recent";
import type { FolderRecord, FolderFormValues } from "../../features/library";
import { Notice } from "../../components/Notice";
import { useTranslate } from "../../i18n/useTranslate";
import { errorText } from "../../services/api/client";
import type { FileItem } from "../../services/api/search";
import "./library-page.css";

export function LibraryPage() {
  const t = useTranslate();
  const [notice, setNotice] = useState("");
  const { filters, updateFilter, resetFilters, searchState, submitSearch } = useFileSearch();
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const [currentFolder, setCurrentFolder] = useState<FolderRecord | null>(null);
  const [showFolderSearch, setShowFolderSearch] = useState(false);
  const moveFilesToRecycle = useMoveFilesToRecycle();
  const recordRecentAccess = useRecordRecentAccess();
  const fileActions = useFileActions();

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

  const [activeDialog, setActiveDialog] = useState<"create" | "edit" | "delete" | null>(null);
  const [selectedFolder, setSelectedFolder] = useState<FolderRecord | undefined>(undefined);
  const [dialogSubmitting, setDialogSubmitting] = useState(false);
  const [dialogError, setDialogError] = useState<string | null>(null);

  function handleResetFilters() {
    resetFilters();
    setNotice(t("search.resetNotice", "筛选条件已重置"));
  }

  function handleSearch() {
    submitSearch(currentFolder ? currentFolder.id : null).then((res) => {
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

  const handleFileTypeChange = (fileType: typeof filters.fileType) => {
    updateFilter("fileType", fileType);
    void submitSearch(currentFolder ? currentFolder.id : null, "relevance", "desc", fileType).then((result) => {
      if (result.ok) {
        setIsSearching(true);
      } else {
        setNotice(result.message);
      }
    });
  };

  const handleOpenFile = async (file: FileItem) => {
    const response = await recordRecentAccess.mutateAsync(file.file_id);
    if (response.status !== "success") {
      setNotice(errorText(response.error) || t("recent.recordFailed", "记录访问失败"));
      return;
    }

    const openFailure = await fileActions.openFile(file);
    setNotice(openFailure ?? `${t("recent.recorded", "已记录访问")} “${file.file_name}”`);
  };

  const handleLocateFile = async (file: FileItem) => {
    const failure = await fileActions.revealFile(file);
    setNotice(failure ?? `${t("search.located", "已定位")} “${file.file_name}”`);
  };

  const refreshSearch = () => {
    void submitSearch(currentFolder ? currentFolder.id : null);
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
              fileType={filters.fileType}
              onFileTypeChange={handleFileTypeChange}
              onNotice={setNotice}
              onMoveToRecycle={handleMoveToRecycle}
              onOpenFile={handleOpenFile}
              onLocateFile={handleLocateFile}
              onRefresh={refreshSearch}
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
              onMoveToRecycle={handleMoveToRecycle}
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
              onFolderAction={(message) => setNotice(message)}
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
    </>
  );
}
