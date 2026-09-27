import { useMemo, useState } from "react";

import { BatchOperationsBar } from "../../components/BatchOperationsBar";
import { DeleteConfirmDialog } from "../../components/DeleteConfirmDialog";
import { Notice } from "../../components/Notice";
import { Pagination } from "../../components/Pagination";
import { RecycleRowItem } from "../../features/recycle/components/RecycleRowItem";
import { useRecycleBin } from "../../features/recycle/hooks/useRecycleBin";
import type { RecycleItem } from "../../services/api/recycle";
import { useTranslate } from "../../i18n/useTranslate";
import { errorText } from "../../services/api/client";

export function RecyclePage() {
  const t = useTranslate();
  const [notice, setNotice] = useState("");
  const { data, loading, error, page, setPage, pageSize, reload, deleteRecords, restoreRecords } = useRecycleBin();
  const [selectedItemIds, setSelectedItemIds] = useState<Set<string>>(new Set());
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);

  const viewResults = useMemo(() => data?.items ?? [], [data]);
  const isBatchMode = selectedItemIds.size > 0;

  const toggleItem = (item: RecycleItem) => {
    setSelectedItemIds((current) => {
      const next = new Set(current);
      if (next.has(item.id)) {
        next.delete(item.id);
      } else {
        next.add(item.id);
      }
      return next;
    });
  };

  const handleLongPress = (itemId: string) => {
    setSelectedItemIds((current) => {
      const next = new Set(current);
      if (next.has(itemId)) {
        next.delete(itemId);
      } else {
        next.add(itemId);
      }
      return next;
    });
    setNotice(t("folder.batchModeActivated", "已开启批量选择模式"));
  };

  const handleSelectAll = () => {
    setSelectedItemIds(new Set(viewResults.map((item) => item.id)));
  };

  const handleInvertSelection = () => {
    setSelectedItemIds((current) => {
      const next = new Set<string>();
      viewResults.forEach((item) => {
        if (!current.has(item.id)) next.add(item.id);
      });
      return next;
    });
  };

  const handleBatchDelete = async () => {
    const itemIds = Array.from(selectedItemIds);
    if (itemIds.length === 0) {
      setConfirmDeleteOpen(false);
      return;
    }

    const response = await deleteRecords.mutateAsync(itemIds);
    setConfirmDeleteOpen(false);
    if (response.status === "success") {
      setNotice(`${t("recycle.batchDeleted", "已彻底删除")} ${itemIds.length} ${t("folder.filesCount", "个文件")}`);
      setSelectedItemIds(new Set());
      void reload();
    } else {
      setNotice(errorText(response.error) || t("recycle.deleteFailed", "永久删除失败"));
    }
  };

  const handleBatchRestore = async () => {
    const itemIds = Array.from(selectedItemIds);
    if (itemIds.length === 0) return;

    const response = await restoreRecords.mutateAsync(itemIds);
    if (response.status === "success") {
      setNotice(`${t("recycle.batchRestored", "已恢复")} ${itemIds.length} ${t("folder.filesCount", "个文件")}`);
      setSelectedItemIds(new Set());
      void reload();
    } else {
      setNotice(errorText(response.error) || t("recycle.restoreFailed", "恢复失败"));
    }
  };

  return (
    <>
      <main className="main-content">
        <section className="search-results-screen" aria-label={t("nav.trash", "回收站")}>
          <div className="results-heading">
            <div className="results-title-group">
              <p>
                <strong>{t("nav.trash", "回收站")}</strong>
              </p>
            </div>
          </div>

          <div className="results-content-split sidebar-collapsed">
            <div className="result-list-container">
              {loading && <div className="results-loading">{t("loading.recycle", "加载中...")}</div>}
              {error && <div className="results-error">{error}</div>}
              {!loading && !error && (
                <div className="result-list" aria-live="polite">
                  {viewResults.length === 0 ? (
                    <div className="empty-results">
                      <p>{t("recycle.empty", "回收站为空")}</p>
                    </div>
                  ) : (
                    viewResults.map((item) => (
                      <RecycleRowItem
                        key={item.id}
                        item={item}
                        isBatchMode={isBatchMode}
                        isRowChecked={selectedItemIds.has(item.id)}
                        onToggleCheck={toggleItem}
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
                    setSelectedItemIds(new Set());
                    setPage(nextPage);
                  }}
                  variant="search"
                />
              )}
            </div>
          </div>
        </section>
      </main>

      {isBatchMode && (
        <BatchOperationsBar
          selectedCount={selectedItemIds.size}
          onSelectAll={handleSelectAll}
          onInvertSelection={handleInvertSelection}
          onRestore={handleBatchRestore}
          onDelete={() => setConfirmDeleteOpen(true)}
          onCancel={() => setSelectedItemIds(new Set())}
          deleteLabel={t("recycle.deletePermanently", "永久删除")}
        />
      )}

      <DeleteConfirmDialog
        isOpen={confirmDeleteOpen}
        onClose={() => setConfirmDeleteOpen(false)}
        onConfirm={handleBatchDelete}
        selectedCount={selectedItemIds.size}
      />

      {notice && <Notice message={notice} onClose={() => setNotice("")} />}
    </>
  );
}
