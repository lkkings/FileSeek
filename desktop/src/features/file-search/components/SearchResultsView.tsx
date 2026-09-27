import { useMemo, useState } from "react";

import { BatchOperationsBar } from "../../../components/BatchOperationsBar";
import { DeleteConfirmDialog } from "../../../components/DeleteConfirmDialog";
import { Icon } from "../../../components/Icon";
import { SortControls } from "../../../components/SortControls";
import { useTranslate } from "../../../i18n/useTranslate";
import type { FileItem, SearchResponseData } from "../../../services/api/search";
import type { FileType } from "../types";
import { FileRowItem } from "./FileRowItem";
import "./search-results.css";

type SortMode = "relevance" | "created_at" | "size";

interface SearchResultsViewProps {
  query: string;
  fileType?: FileType;
  onFileTypeChange?: (fileType: FileType) => void;
  onNotice: (message: string) => void;
  onMoveToRecycle?: (fileIds: string[]) => Promise<boolean>;
  onOpenFile?: (file: FileItem) => void | Promise<void>;
  onLocateFile?: (file: FileItem) => void | Promise<void>;
  onRefresh?: () => void;
  data?: SearchResponseData | undefined;
  status?: "success" | "error" | "loading" | "idle";
  error?: string | null;
  onBack?: () => void;
}

const TYPE_OPTIONS: Array<{ id: FileType; labelId: string; label: string; icon: "archive" | "document" | "image" | "video" }> = [
  { id: "all", labelId: "fileType.all", label: "全部", icon: "archive" },
  { id: "document", labelId: "fileType.document", label: "文档", icon: "document" },
  { id: "image", labelId: "fileType.image", label: "图片", icon: "image" },
  { id: "video", labelId: "fileType.video", label: "视频", icon: "video" },
];

export function SearchResultsView({
  query,
  fileType = "all",
  onFileTypeChange,
  onNotice,
  onMoveToRecycle,
  onOpenFile,
  onLocateFile,
  onRefresh,
  data,
  status,
  error,
  onBack,
}: SearchResultsViewProps) {
  const t = useTranslate();
  const [sortMode, setSortMode] = useState<SortMode>("relevance");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");
  const [selectedItemIds, setSelectedItemIds] = useState<Set<string>>(new Set());
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);

  const viewResults = useMemo<FileItem[]>(() => data?.items ?? [], [data]);
  const visibleResults = useMemo(() => {
    const results = [...viewResults];
    results.sort((left, right) => {
      let comparison: number;
      if (sortMode === "size") {
        comparison = (left.size ?? 0) - (right.size ?? 0);
      } else if (sortMode === "created_at") {
        comparison = (left.modified ?? "").localeCompare(right.modified ?? "");
      } else {
        comparison = left.score - right.score;
      }
      return sortOrder === "asc" ? comparison : -comparison;
    });
    return results;
  }, [sortMode, sortOrder, viewResults]);

  const isBatchMode = selectedItemIds.size > 0;

  const countByType = (type: FileType) => {
    if (type === "all") return viewResults.length;
    return viewResults.filter((file) => file.category === type).length;
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
    onNotice(t("folder.batchModeActivated", "已开启批量选择模式"));
  };

  const handleSelectAll = () => {
    setSelectedItemIds(new Set(visibleResults.map((file) => file.file_id)));
  };

  const handleInvertSelection = () => {
    setSelection((current) => {
      const next = new Set<string>();
      visibleResults.forEach((file) => {
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

    const success = await onMoveToRecycle(fileIds);
    if (success) {
      onNotice(`${t("recycle.batchMoved", "已移入回收站")} ${fileIds.length} ${t("folder.filesCount", "个文件")}`);
      setSelectedItemIds(new Set());
      setConfirmDeleteOpen(false);
      onRefresh?.();
    } else {
      onNotice(t("recycle.moveFailed", "移入回收站失败"));
    }
  };

  const handleOpenFile = (file: FileItem) => {
    if (onOpenFile) void onOpenFile(file);
    else onNotice(`${t("folder.fileActionsFor", "已查看文件操作")} “${file.file_name}”`);
  };

  const handleLocateFile = (file: FileItem) => {
    if (onLocateFile) void onLocateFile(file);
    else onNotice(`${t("search.locateFile", "在文件夹中显示")} “${file.file_name}”`);
  };

  return (
    <div className="results-workspace">
      <div className="result-tabs" role="tablist" aria-label={t("search.type.label", "文件类型")}>
        {TYPE_OPTIONS.map((option) => (
          <button
            key={option.id}
            type="button"
            role="tab"
            aria-selected={fileType === option.id}
            className={`result-tab ${fileType === option.id ? "is-active" : ""}`}
            onClick={() => onFileTypeChange?.(option.id)}
          >
            <Icon name={option.icon} size={18} />
            <span>{t(option.labelId, option.label)}</span>
            <span className="tab-count">{countByType(option.id)}</span>
          </button>
        ))}
      </div>

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
            <span>({viewResults.length})</span>
            <em>“{query}”</em>
          </p>
        </div>
        <SortControls
          options={[
            { value: "relevance", label: t("search.sortRelevance", "相关度") },
            { value: "size", label: t("search.sortSize", "文件大小") },
            { value: "created_at", label: t("search.sortModified", "按修改时间") },
          ]}
          sortBy={sortMode}
          sortOrder={sortOrder}
          onSortByChange={(value) => setSortMode(value as SortMode)}
          onSortOrderChange={setSortOrder}
        />
      </div>

      {status === "loading" && <div className="results-loading">{t("loading.search", "加载中...")}</div>}
      {error && <div className="results-error">{error}</div>}

      {status !== "loading" && !error && (
        <div className="result-list" aria-live="polite">
          {visibleResults.length === 0 ? (
            <div className="empty-results">
              <Icon name="search" size={28} />
              <p>{t("search.empty", "没有找到匹配的文件")}</p>
            </div>
          ) : (
            visibleResults.map((file) => (
              <FileRowItem
                key={file.file_id}
                file={file}
                isSelected={false}
                isBatchMode={isBatchMode}
                isRowChecked={selectedItemIds.has(file.file_id)}
                onRowClick={handleOpenFile}
                onToggleCheck={handleToggleCheck}
                onLongPress={handleLongPress}
                onOpenFile={handleOpenFile}
                onLocateFile={handleLocateFile}
              />
            ))
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
