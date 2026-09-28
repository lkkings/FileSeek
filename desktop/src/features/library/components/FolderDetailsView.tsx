import { useMemo, useState } from "react";

import { BatchOperationsBar } from "../../../components/BatchOperationsBar";
import { DeleteConfirmDialog } from "../../../components/DeleteConfirmDialog";
import { FileDetailDrawer } from "../../../components/FileDetailDrawer";
import { Icon, type IconName } from "../../../components/Icon";
import { Pagination } from "../../../components/Pagination";
import { SortControls } from "../../../components/SortControls";
import { useTranslate } from "../../../i18n/useTranslate";
import type { FileItem } from "../../../services/api/search";
import { useFolderFiles } from "../hooks/useFolderFiles";
import type { FolderRecord } from "../types";
import { FileGridItem } from "./FileGridItem";
import { FileListView } from "./FileListView";
import { MoveFilesDialog } from "./MoveFilesDialog";
import { TagFilterSelector } from "./TagFilterSelector";
import "./folder-details.css";

interface FolderDetailsViewProps {
  folder: FolderRecord;
  onBack: () => void;
  onFolderAction: (message: string) => void;
  onToggleSearch: () => void;
  isSearchActive: boolean;
  folders: FolderRecord[];
  onMoveToRecycle: (fileIds: string[]) => Promise<boolean>;
  onMoveToFolder: (fileIds: string[], targetFolderId: string) => Promise<boolean>;
  onOpenFile: (file: FileItem) => void | Promise<void>;
}

type SortMode = "created_at" | "size";
type Category = "all" | "document" | "image" | "video";
type ViewMode = "grid" | "list";

const PAGE_SIZE = 12;

const CATEGORY_OPTIONS: Array<{
  id: Category;
  labelId: string;
  label: string;
  icon: IconName;
}> = [
  { id: "all", labelId: "fileType.all", label: "全部", icon: "archive" },
  { id: "document", labelId: "fileType.document", label: "文档", icon: "document" },
  { id: "image", labelId: "fileType.image", label: "图片", icon: "image" },
  { id: "video", labelId: "fileType.video", label: "视频", icon: "video" },
];

export function FolderDetailsView({
  folder,
  onBack,
  onFolderAction,
  onToggleSearch,
  isSearchActive,
  folders,
  onMoveToRecycle,
  onMoveToFolder,
  onOpenFile,
}: FolderDetailsViewProps) {
  const t = useTranslate();
  const [sortMode, setSortMode] = useState<SortMode>("created_at");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");
  const [category, setCategory] = useState<Category>("all");
  const [tag, setTag] = useState("全部");
  const [pageNumber, setPageNumber] = useState(1);
  const [viewMode, setViewMode] = useState<ViewMode>("grid");
  const [detailFile, setDetailFile] = useState<FileItem | null>(null);
  const [selectedItemIds, setSelectedItemIds] = useState<Set<string>>(new Set());
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);
  const [moveDialogOpen, setMoveDialogOpen] = useState(false);
  const [recycleSubmitting, setRecycleSubmitting] = useState(false);
  const [moveSubmitting, setMoveSubmitting] = useState(false);

  const { data, loading, error, total, reload } = useFolderFiles({
    folderId: folder.id,
    category,
    tag,
    sortBy: sortMode,
    sortOrder,
    pageNumber,
    pageSize: PAGE_SIZE,
  });

  const viewResults = useMemo<FileItem[]>(() => {
    const results = [...(data?.items ?? [])];
    results.sort((left, right) => {
      const comparison = sortMode === "size"
        ? (left.size ?? 0) - (right.size ?? 0)
        : (left.modified ?? "").localeCompare(right.modified ?? "");
      return sortOrder === "asc" ? comparison : -comparison;
    });
    return results;
  }, [data, sortMode, sortOrder]);

  const isBatchMode = selectedItemIds.size > 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const currentPage = Math.min(pageNumber, totalPages);

  const countByCategory = (categoryId: Category) => {
    if (categoryId === "all") return total;
    const counterValue = data?.counter?.[categoryId];
    if (typeof counterValue === "number") return counterValue;
    return viewResults.filter((file) => file.category === categoryId).length;
  };

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
    onFolderAction(t("folder.batchModeActivated", "已开启批量选择模式"));
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
    const fileIds = Array.from(selectedItemIds);
    if (fileIds.length === 0) {
      setConfirmDeleteOpen(false);
      return;
    }

    setRecycleSubmitting(true);
    try {
      const success = await onMoveToRecycle(fileIds);
      if (success) {
        onFolderAction(`${t("recycle.batchMoved", "已移入回收站")} ${fileIds.length} ${t("folder.filesCount", "个文件")}`);
        setSelectedItemIds(new Set());
        setConfirmDeleteOpen(false);
        reload();
      } else {
        onFolderAction(t("recycle.moveFailed", "移入回收站失败"));
      }
    } finally {
      setRecycleSubmitting(false);
    }
  };

  const handleBatchMove = async (targetFolderId: string) => {
    const fileIds = Array.from(selectedItemIds);
    if (fileIds.length === 0) {
      setMoveDialogOpen(false);
      return;
    }

    setMoveSubmitting(true);
    try {
      const success = await onMoveToFolder(fileIds, targetFolderId);
      if (success) {
        onFolderAction(`${t("folder.batchMoved", "已移动")} ${fileIds.length} ${t("folder.filesCount", "个文件")}`);
        setSelectedItemIds(new Set());
        setMoveDialogOpen(false);
        reload();
      } else {
        onFolderAction(t("folder.moveFailed", "移动文件失败"));
      }
    } finally {
      setMoveSubmitting(false);
    }
  };

  const handleCategoryChange = (nextCategory: Category) => {
    setCategory(nextCategory);
    setPageNumber(1);
    setSelectedItemIds(new Set());
  };

  const handleTagChange = (nextTag: string) => {
    setTag(nextTag);
    setPageNumber(1);
    setSelectedItemIds(new Set());
  };

  const handlePageChange = (nextPage: number) => {
    if (nextPage < 1 || nextPage > totalPages || nextPage === currentPage) return;
    setPageNumber(nextPage);
    setSelectedItemIds(new Set());
  };

  const handleFileDetail = (file: FileItem) => {
    setDetailFile(file);
  };

  const handleFilePreview = (file: FileItem) => {
    setDetailFile(null);
    void onOpenFile(file);
  };

  return (
    <div className="folder-details-view">
      <header className="details-header">
        <div className="breadcrumbs-container">
          <button className="btn-icon-back" type="button" onClick={onBack} aria-label={t("search.back", "返回")}>
            <Icon name="chevron" size={20} />
          </button>
          <nav className="breadcrumbs-path" aria-label={t("folder.breadcrumb", "文件夹路径")}>
            <button className="path-crumb" type="button" onClick={onBack}>
              {t("nav.library", "资源库")}
            </button>
            <span className="path-separator">/</span>
            <span className="path-active">{folder.name}</span>
          </nav>
        </div>

        <div className="header-right-actions">
          <button
            className={`btn-folder-search-toggle ${isSearchActive ? "is-active" : ""}`}
            type="button"
            onClick={onToggleSearch}
            aria-pressed={isSearchActive}
            aria-label={t("folder.search", "在当前文件夹内搜索")}
          >
            <Icon name="search" size={18} />
          </button>
        </div>
      </header>

      <div className="filter-row">
        <div className="category-filter-tabs" role="tablist" aria-label={t("search.type.label", "文件类型")}>
          {CATEGORY_OPTIONS.map((option) => (
            <button
              key={option.id}
              type="button"
              role="tab"
              aria-selected={category === option.id}
              className={`category-tab-btn ${category === option.id ? "is-active" : ""}`}
              onClick={() => handleCategoryChange(option.id)}
            >
              <Icon name={option.icon} size={16} />
              <span>{t(option.labelId, option.label)}</span>
              <span className="category-tab-count">{countByCategory(option.id)}</span>
            </button>
          ))}
        </div>
      </div>

      <TagFilterSelector selectedTag={tag} onTagChange={handleTagChange} />

      <div className="details-sub-actions-bar">
        <div className="sort-selection-group">
          <div className="view-layout-toggles" role="group" aria-label={t("folder.viewMode", "视图模式")}>
            <button
              className={`btn-layout-toggle ${viewMode === "grid" ? "is-active" : ""}`}
              type="button"
              onClick={() => setViewMode("grid")}
              aria-pressed={viewMode === "grid"}
              aria-label={t("folder.gridView", "网格视图")}
            >
              <Icon name="grid" size={18} />
            </button>
            <button
              className={`btn-layout-toggle ${viewMode === "list" ? "is-active" : ""}`}
              type="button"
              onClick={() => setViewMode("list")}
              aria-pressed={viewMode === "list"}
              aria-label={t("folder.listView", "列表视图")}
            >
              <Icon name="list" size={18} />
            </button>
          </div>
          <SortControls
            options={[
              { value: "created_at", label: t("search.sortModified", "按修改时间") },
              { value: "size", label: t("search.sortSize", "文件大小") },
            ]}
            sortBy={sortMode}
            sortOrder={sortOrder}
            onSortByChange={(value) => {
              setSortMode(value as SortMode);
              setPageNumber(1);
            }}
            onSortOrderChange={setSortOrder}
          />
        </div>
      </div>

      {loading && <div className="results-loading">{t("loading.files", "加载文件夹内容...")}</div>}
      {error && <div className="results-error">{error}</div>}

      {!loading && !error && (
        <>
          {viewMode === "grid" ? (
            <div className="files-grid-container" aria-live="polite">
              {viewResults.map((file) => (
                <FileGridItem
                  key={file.file_id}
                  file={file}
                  isBatchMode={isBatchMode}
                  isCardChecked={selectedItemIds.has(file.file_id)}
                  onCardClick={handleFileDetail}
                  onCardDoubleClick={handleFilePreview}
                  onToggleCheck={handleToggleCheck}
                  onLongPress={handleLongPress}
                />
              ))}
              {viewResults.length === 0 && (
                <div className="empty-results">
                  <Icon name="folder" size={28} />
                  <p>{t("folder.empty", "文件夹为空")}</p>
                </div>
              )}
            </div>
          ) : (
            <>
              <FileListView
                files={viewResults}
                isBatchMode={isBatchMode}
              selectedFileIds={selectedItemIds}
              onRowClick={handleFileDetail}
              onRowDoubleClick={handleFilePreview}
              onToggleCheck={handleToggleCheck}
              onLongPress={handleLongPress}
              />
              {viewResults.length === 0 && (
                <div className="empty-results">
                  <Icon name="folder" size={28} />
                  <p>{t("folder.empty", "文件夹为空")}</p>
                </div>
              )}
            </>
          )}

          <Pagination
            currentPage={currentPage}
            totalPages={totalPages}
            totalItems={total}
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
        title={t("recycle.confirmMoveTitle", "确认移入回收站")}
        description={t("recycle.confirmMoveDescription", "确定要将这")}
        confirmLabel={t("recycle.moveToTrash", "移入回收站")}
      />

      {moveDialogOpen && (
        <MoveFilesDialog
          folders={folders}
          currentFolderId={folder.id}
          selectedCount={selectedItemIds.size}
          submitting={moveSubmitting}
          onClose={() => {
            if (!moveSubmitting) setMoveDialogOpen(false);
          }}
          onConfirm={handleBatchMove}
        />
      )}

      <FileDetailDrawer
        isOpen={detailFile !== null}
        onClose={() => setDetailFile(null)}
        file={detailFile}
        onOpenAction={handleFilePreview}
      />
    </div>
  );
}
