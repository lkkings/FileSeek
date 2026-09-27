import { useMemo, useState } from "react";

import { BatchOperationsBar } from "../../components/BatchOperationsBar";
import { DeleteConfirmDialog } from "../../components/DeleteConfirmDialog";
import { FileDetailDrawer } from "../../components/FileDetailDrawer";
import { Notice } from "../../components/Notice";
import { Pagination } from "../../components/Pagination";
import { FileRowItem } from "../../features/file-search/components/FileRowItem";
import { useRecentAccess } from "../../features/recent/hooks/useRecentAccess";
import { useRecordRecentAccess } from "../../features/recent/hooks/useRecordRecentAccess";
import type { RecentRecord } from "../../features/recent/types";
import { useTranslate } from "../../i18n/useTranslate";
import { errorText } from "../../services/api/client";
import type { FileItem } from "../../services/api/search";
import "../../features/file-search/components/search-results.css";

export function RecentPage() {
  const t = useTranslate();
  const [notice, setNotice] = useState("");
  const { data, loading, error, page, setPage, pageSize, reload, deleteRecords } = useRecentAccess();
  const recordAccess = useRecordRecentAccess();
  const [selectedRecordIds, setSelectedRecordIds] = useState<Set<number>>(new Set());
  const [selectedFileId, setSelectedFileId] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);

  const viewResults = useMemo(() => data?.items ?? [], [data]);
  const isBatchMode = selectedRecordIds.size > 0;

  const toggleRecord = (record: RecentRecord) => {
    setSelectedRecordIds((current) => {
      const next = new Set(current);
      if (next.has(record.recordId)) {
        next.delete(record.recordId);
      } else {
        next.add(record.recordId);
      }
      return next;
    });
  };

  const handleLongPress = (fileId: string) => {
    const record = viewResults.find((item) => item.file.file_id === fileId);
    if (!record) return;
    toggleRecord(record);
    setNotice(t("folder.batchModeActivated", "已开启批量选择模式"));
  };

  const handleSelectAll = () => {
    setSelectedRecordIds(new Set(viewResults.map((record) => record.recordId)));
  };

  const handleInvertSelection = () => {
    setSelectedRecordIds((current) => {
      const next = new Set<number>();
      viewResults.forEach((record) => {
        if (!current.has(record.recordId)) next.add(record.recordId);
      });
      return next;
    });
  };

  const handleBatchDelete = async () => {
    const recordIds = Array.from(selectedRecordIds);
    if (recordIds.length === 0) {
      setConfirmDeleteOpen(false);
      return;
    }

    const result = await deleteRecords.mutateAsync(recordIds);
    setConfirmDeleteOpen(false);
    setSelectedRecordIds(new Set(result.failedRecordIds));

    if (result.failureCount === 0) {
      setNotice(`${t("recent.batchDeleted", "已删除")} ${result.successCount} ${t("recent.recordsUnit", "条访问记录")}`);
      void reload();
      return;
    }

    if (result.successCount > 0) {
      setNotice(`${t("recent.partialDelete", "部分删除成功")}: ${result.successCount}/${recordIds.length}`);
      void reload();
    } else {
      setNotice(result.errors[0] || t("recent.deleteFailed", "删除访问记录失败"));
    }
  };

  const handleSelectRow = (file: FileItem) => {
    setSelectedFileId(file.file_id);
    setSidebarOpen(true);
  };

  const handleOpenFile = async (file: FileItem) => {
    const response = await recordAccess.mutateAsync(file.file_id);
    if (response.status === "success") {
      setNotice(`${t("recent.recorded", "已记录访问")} “${file.file_name}”`);
      void reload();
    } else {
      setNotice(errorText(response.error) || t("recent.recordFailed", "记录访问失败"));
    }
  };

  const selectedItem = useMemo(() => {
    return viewResults.find((record) => record.file.file_id === selectedFileId)?.file ?? null;
  }, [selectedFileId, viewResults]);

  return (
    <>
      <main className="main-content">
        <section className="search-results-screen" aria-label={t("nav.recent", "最近访问")}>
          <div className="results-heading">
            <div className="results-title-group">
              <p>
                <strong>{t("nav.recent", "最近访问")}</strong>
              </p>
            </div>
          </div>

          <div className={`results-content-split ${sidebarOpen && selectedItem ? "sidebar-expanded" : "sidebar-collapsed"}`}>
            <div className="result-list-container">
              {loading && <div className="results-loading">{t("loading.recent", "加载中...")}</div>}
              {error && <div className="results-error">{error}</div>}
              {!loading && !error && (
                <div className="result-list" aria-live="polite">
                  {viewResults.length === 0 ? (
                    <div className="empty-results">
                      <p>{t("recent.empty", "暂无访问记录")}</p>
                    </div>
                  ) : (
                    viewResults.map((record) => (
                      <FileRowItem
                        key={record.recordId}
                        file={record.file}
                        isSelected={selectedFileId === record.file.file_id}
                        isBatchMode={isBatchMode}
                        isRowChecked={selectedRecordIds.has(record.recordId)}
                        onRowClick={handleSelectRow}
                        onToggleCheck={() => toggleRecord(record)}
                        onLongPress={handleLongPress}
                      />
                    ))
                  )}
                </div>
              )}
              {!loading && !error && data && data.total > 0 && (
                <Pagination
                  currentPage={page}
                  totalPages={Math.ceil(data.total / pageSize)}
                  totalItems={data.total}
                  onPageChange={(nextPage) => {
                    setSelectedRecordIds(new Set());
                    setPage(nextPage);
                  }}
                  variant="search"
                />
              )}
            </div>

            <FileDetailDrawer
              isOpen={sidebarOpen && !!selectedItem}
              onClose={() => setSidebarOpen(false)}
              file={selectedItem}
              onOpenAction={handleOpenFile}
            />
          </div>
        </section>
      </main>

      {isBatchMode && (
        <BatchOperationsBar
          selectedCount={selectedRecordIds.size}
          onSelectAll={handleSelectAll}
          onInvertSelection={handleInvertSelection}
          onDelete={() => setConfirmDeleteOpen(true)}
          onCancel={() => setSelectedRecordIds(new Set())}
        />
      )}

      <DeleteConfirmDialog
        isOpen={confirmDeleteOpen}
        onClose={() => setConfirmDeleteOpen(false)}
        onConfirm={handleBatchDelete}
        selectedCount={selectedRecordIds.size}
      />

      {notice && <Notice message={notice} onClose={() => setNotice("")} />}
    </>
  );
}
