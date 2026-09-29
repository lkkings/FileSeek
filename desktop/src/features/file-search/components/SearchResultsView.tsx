import { useState } from "react";

import { BatchOperationsBar } from "../../../components/BatchOperationsBar";
import { DeleteConfirmDialog } from "../../../components/DeleteConfirmDialog";
import { FileDetailDrawer } from "../../../components/FileDetailDrawer";
import { FileListRow } from "../../../components/FileListRow";
import { Icon } from "../../../components/Icon";
import { MoveToFolderDialog } from "../../../components/MoveToFolderDialog";
import { Pagination } from "../../../components/Pagination";
import { SortControls } from "../../../components/SortControls";
import { useTranslate } from "../../../i18n/useTranslate";
import { formatSearchMatchNotice } from "../utils/searchMatch";
import type { FileItem, SearchResponseData } from "../../../services/api/search";
import "./search-results.css";

type SortMode = "relevance" | "created_at" | "size";
type SortOrder = "asc" | "desc";

interface FolderOption {
  id: string;
  name: string;
}

interface SearchResultsViewProps {
  query: string;
  onNotice: (message: string) => void;
  onMoveToRecycle?: (fileIds: string[]) => Promise<boolean>;
  onMoveToFolder?: (fileIds: string[], targetFolderId: string) => Promise<boolean>;
  folders?: FolderOption[];
  foldersLoading?: boolean;
  foldersError?: string | null;
  searchScopeFolderId?: string | null;
  onOpenFile?: (file: FileItem) => void | Promise<void>;
  onRefresh?: () => void;
  onPageChange?: (pageNumber: number) => void;
  currentPage?: number;
  pageSize?: number;
  totalItems?: number;
  sortBy?: SortMode;
  sortOrder?: SortOrder;
  onSortByChange?: (sortBy: SortMode) => void;
  onSortOrderChange?: (sortOrder: SortOrder) => void;
  data?: SearchResponseData | undefined;
  status?: "success" | "error" | "loading" | "idle";
  error?: string | null;
  onBack?: () => void;
}

export function SearchResultsView({
  query,
  onNotice,
  onMoveToRecycle,
  onMoveToFolder,
  folders = [],
  foldersLoading = false,
  foldersError = null,
  searchScopeFolderId = null,
  onOpenFile,
  onRefresh,
  onPageChange,
  currentPage,
  pageSize,
  totalItems,
  sortBy = "relevance",
  sortOrder = "desc",
  onSortByChange,
  onSortOrderChange,
  data,
  status,
  error,
  onBack,
}: SearchResultsViewProps) {
  const t = useTranslate();
  const [selectedItemIds, setSelectedItemIds] = useState<Set<string>>(new Set());
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);
  const [recycleSubmitting, setRecycleSubmitting] = useState(false);
  const [moveDialogOpen, setMoveDialogOpen] = useState(false);
  const [moveSubmitting, setMoveSubmitting] = useState(false);
  const [detailFile, setDetailFile] = useState<FileItem | null>(null);

  const viewResults = data?.items ?? [];
  const itemCount = totalItems ?? data?.total ?? viewResults.length;
  const itemPageSize = pageSize ?? data?.page_size ?? 20;
  const itemCurrentPage = currentPage ?? data?.page_number ?? 1;
  const totalPages = Math.max(1, Math.ceil(itemCount / itemPageSize));
  const isBatchMode = selectedItemIds.size > 0;

  const setSelection = (updater: (current: Set<string>) => Set<string>) => {
    setSelectedItemIds((current) => new Set(updater(current)));
  };

  const handleToggleCheck = (file: FileItem) => {
    setSelection((current) => {
      const next = new Set(current);
      if (next.has(file.file_id)) next.delete(file.file_id);
      else next.add(file.file_id);
      return next;
    });
  };

  const handleLongPress = (fileId: string) => {
    setSelection((current) => {
      const next = new Set(current);
      if (next.has(fileId)) next.delete(fileId);
      else next.add(fileId);
      return next;
    });
    onNotice(t("folder.batchModeActivated", "已开启批量选择模式"));
  };

  const handleSelectAll = () => {
    setSelectedItemIds(new Set(viewResults.map((file) => file.file_id)));
  };

  const handleInvertSelection = () => {
    setSelection((current) => {
      const next = new Set<string>();
      viewResults.forEach((file) => {
        if (!current.has(file.file_id)) next.add(file.file_id);
      });
      return next;
    });
  };

  const handleBatchDelete = async () => {
    if (!onMoveToRecycle) return;
    const fileIds = Array.from(selectedItemIds);
    if (fileIds.length === 0) {
      setConfirmDeleteOpen(false);
      return;
    }

    setRecycleSubmitting(true);
    try {
      const success = await onMoveToRecycle(fileIds);
      if (success) {
        onNotice(`${t("recycle.batchMoved", "已移入回收站")} ${fileIds.length} ${t("folder.filesCount", "个文件")}`);
        setSelectedItemIds(new Set());
        setConfirmDeleteOpen(false);
        onRefresh?.();
      } else {
        onNotice(t("recycle.moveFailed", "移入回收站失败"));
      }
    } finally {
      setRecycleSubmitting(false);
    }
  };

  const handleBatchMove = async (targetFolderId: string) => {
    if (!onMoveToFolder) return;
    const fileIds = Array.from(selectedItemIds);
    if (fileIds.length === 0) {
      setMoveDialogOpen(false);
      return;
    }

    setMoveSubmitting(true);
    try {
      const success = await onMoveToFolder(fileIds, targetFolderId);
      if (success) {
        onNotice(`${t("folder.batchMoved", "已移动")} ${fileIds.length} ${t("folder.filesCount", "个文件")}`);
        setSelectedItemIds(new Set());
        setMoveDialogOpen(false);
        onRefresh?.();
      } else {
        onNotice(t("folder.moveFailed", "移动文件失败"));
      }
    } finally {
      setMoveSubmitting(false);
    }
  };

  const handleOpenFile = (file: FileItem) => {
    if (onOpenFile) void onOpenFile(file);
    else onNotice(`${t("folder.fileActionsFor", "已查看文件操作")} “${file.file_name}”`);
  };

  const handlePageChange = (nextPage: number) => {
    setSelectedItemIds(new Set());
    setDetailFile(null);
    onPageChange?.(nextPage);
  };

  const handleSortByChange = (nextSortBy: SortMode) => {
    setSelectedItemIds(new Set());
    setDetailFile(null);
    onSortByChange?.(nextSortBy);
  };

  const handleSortOrderChange = (nextSortOrder: SortOrder) => {
    setSelectedItemIds(new Set());
    setDetailFile(null);
    onSortOrderChange?.(nextSortOrder);
  };

  return (
    <div className="results-workspace">
      <div className="results-heading">
        <div className="results-title-group">
          {onBack && (
            <button className="back-button" type="button" onClick={onBack}>
              <Icon name="chevron" size={18} />
              <span>{t("search.back", "返回")}</span>
            </button>
          )}
          <p>
            <strong>{t("search.resultsTitle", "搜索结果")}</strong>
            <span>({itemCount})</span>
            <em>“{query}”</em>
          </p>
        </div>
        <SortControls
          options={[
            { value: "relevance", label: t("search.sortRelevance", "相关度") },
            { value: "size", label: t("search.sortSize", "文件大小") },
            { value: "created_at", label: t("search.sortModified", "按修改时间") },
          ]}
          sortBy={sortBy}
          sortOrder={sortOrder}
          onSortByChange={(value) => handleSortByChange(value as SortMode)}
          onSortOrderChange={handleSortOrderChange}
        />
      </div>

      {status === "loading" && <div className="results-loading">{t("loading.search", "加载中...")}</div>}
      {error && <div className="results-error">{error}</div>}

      {status !== "loading" && !error && (
        <>
          <div className="result-list" aria-live="polite">
            {viewResults.length === 0 ? (
              <div className="empty-results">
                <Icon name="search" size={28} />
                <p>{t("search.empty", "没有找到匹配的文件")}</p>
              </div>
            ) : (
              viewResults.map((file) => (
                <FileListRow
                  key={file.file_id}
                  file={file}
                  isBatchMode={isBatchMode}
                  isRowChecked={selectedItemIds.has(file.file_id)}
                  onRowClick={setDetailFile}
                  onRowDoubleClick={handleOpenFile}
                  onToggleCheck={handleToggleCheck}
                  onLongPress={handleLongPress}
                  showTime
                />
              ))
            )}
          </div>

          <Pagination
            currentPage={itemCurrentPage}
            totalPages={totalPages}
            totalItems={itemCount}
            onPageChange={handlePageChange}
            variant="details"
          />
        </>
      )}

      {isBatchMode && (
        <BatchOperationsBar
          selectedCount={selectedItemIds.size}
          onSelectAll={handleSelectAll}
          onInvertSelection={handleInvertSelection}
          onDelete={() => setConfirmDeleteOpen(true)}
          onMoveTo={() => setMoveDialogOpen(true)}
          onCancel={() => setSelectedItemIds(new Set())}
          deleteLabel={t("recycle.moveToTrash", "移入回收站")}
        />
      )}

      <DeleteConfirmDialog
        isOpen={confirmDeleteOpen}
        onClose={() => setConfirmDeleteOpen(false)}
        onConfirm={handleBatchDelete}
        selectedCount={selectedItemIds.size}
        confirmDisabled={recycleSubmitting}
      />

      <MoveToFolderDialog
        isOpen={moveDialogOpen}
        folders={folders}
        loading={foldersLoading}
        error={foldersError}
        excludeFolderId={searchScopeFolderId}
        selectedCount={selectedItemIds.size}
        submitting={moveSubmitting}
        onClose={() => {
          if (!moveSubmitting) setMoveDialogOpen(false);
        }}
        onConfirm={(targetFolderId) => void handleBatchMove(targetFolderId)}
      />

      <FileDetailDrawer
        isOpen={detailFile !== null}
        onClose={() => setDetailFile(null)}
        file={detailFile}
        onOpenAction={handleOpenFile}
        matchInfo={formatSearchMatchNotice(detailFile?.metadata, t)}
      />
    </div>
  );
}
