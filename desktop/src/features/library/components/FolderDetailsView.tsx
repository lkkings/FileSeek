import { useMemo, useState } from "react";

import { BatchOperationsBar } from "../../../components/BatchOperationsBar";
import { DeleteConfirmDialog } from "../../../components/DeleteConfirmDialog";
import { FileTableRow } from "../../../components/FileTableRow";
import { Icon, type IconName } from "../../../components/Icon";
import { SortControls } from "../../../components/SortControls";
import { useTranslate } from "../../../i18n/useTranslate";
import type { FileItem } from "../../../services/api/search";
import { useFolderFiles } from "../hooks/useFolderFiles";
import type { FolderRecord } from "../types";
import "./folder-details.css";

interface FolderDetailsViewProps {
  folder: FolderRecord;
  onBack: () => void;
  onFolderAction: (message: string) => void;
  onToggleSearch: () => void;
  isSearchActive: boolean;
  onMoveToRecycle: (fileIds: string[]) => Promise<boolean>;
  onOpenFile: (file: FileItem) => void | Promise<void>;
}

type SortMode = "created_at" | "size";

export function FolderDetailsView({
  folder,
  onBack,
  onFolderAction,
  onToggleSearch,
  isSearchActive,
  onMoveToRecycle,
  onOpenFile,
}: FolderDetailsViewProps) {
  const t = useTranslate();
  const [sortMode, setSortMode] = useState<SortMode>("created_at");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");
  const [selectedItemIds, setSelectedItemIds] = useState<Set<string>>(new Set());
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);

  const { data, loading, error, reload } = useFolderFiles({
    folderId: folder.id,
    sortBy: sortMode,
    sortOrder,
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

    const success = await onMoveToRecycle(fileIds);
    if (success) {
      onFolderAction(`${t("recycle.batchMoved", "已移入回收站")} ${fileIds.length} ${t("folder.filesCount", "个文件")}`);
      setSelectedItemIds(new Set());
      setConfirmDeleteOpen(false);
      reload();
    } else {
      onFolderAction(t("recycle.moveFailed", "移入回收站失败"));
    }
  };

  return (
    <div className="folder-details-table-page">
      <div className="results-heading">
        <div className="results-title-group">
          <button className="back-button" type="button" onClick={onBack}>
            <Icon name="chevron" size={18} />
            <span>{t("search.back", "返回")}</span>
          </button>
          <div className="folder-details-title">
            <Icon name={folder.iconType as IconName} size={24} />
            <h2>{folder.name}</h2>
          </div>
        </div>
        <div className="folder-details-controls">
          <button
            className={`sidebar-action-btn folder-search-toggle ${isSearchActive ? "btn-primary" : ""}`}
            type="button"
            onClick={onToggleSearch}
            title={t("folder.search", "在当前文件夹内搜索")}
          >
            <Icon name="search" size={18} />
          </button>
          <SortControls
            options={[
              { value: "created_at", label: t("search.sortModified", "按修改时间") },
              { value: "size", label: t("search.sortSize", "文件大小") },
            ]}
            sortBy={sortMode}
            sortOrder={sortOrder}
            onSortByChange={(value) => setSortMode(value as SortMode)}
            onSortOrderChange={setSortOrder}
          />
        </div>
      </div>

      {loading && <div className="results-loading">{t("loading.files", "加载文件夹内容...")}</div>}
      {error && <div className="results-error">{error}</div>}

      {!loading && !error && (
        <div className="file-library__table-wrapper">
          <table className="file-library__table">
            <thead>
              <tr>
                {isBatchMode && <th>{t("batch.selected", "选择")}</th>}
                <th>{t("lib.name", "文件名")}</th>
                <th>{t("lib.size", "大小")}</th>
                <th>{t("lib.modifiedDate", "修改时间")}</th>
                <th>{t("search.colPath", "路径")}</th>
                <th>{t("ingest.action", "操作")}</th>
              </tr>
            </thead>
            <tbody>
              {viewResults.map((file) => (
                <FileTableRow
                  key={file.file_id}
                  file={file}
                  variant="folder"
                  isBatchMode={isBatchMode}
                  isRowChecked={selectedItemIds.has(file.file_id)}
                  onToggleCheck={handleToggleCheck}
                  onLongPress={handleLongPress}
                  onOpenFile={(selectedFile) => void onOpenFile(selectedFile)}
                />
              ))}
            </tbody>
          </table>
          {viewResults.length === 0 && (
            <div className="empty-results">
              <Icon name="folder" size={28} />
              <p>{t("folder.empty", "文件夹为空")}</p>
            </div>
          )}
        </div>
      )}

      {isBatchMode && (
        <BatchOperationsBar
          selectedCount={selectedItemIds.size}
          onSelectAll={handleSelectAll}
          onInvertSelection={handleInvertSelection}
          onDelete={() => setConfirmDeleteOpen(true)}
          onCancel={() => setSelectedItemIds(new Set())}
          deleteLabel={t("recycle.moveToTrash", "移入回收站")}
        />
      )}

      <DeleteConfirmDialog
        isOpen={confirmDeleteOpen}
        onClose={() => setConfirmDeleteOpen(false)}
        onConfirm={handleBatchDelete}
        selectedCount={selectedItemIds.size}
      />
    </div>
  );
}
