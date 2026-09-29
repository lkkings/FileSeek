import { useMemo, useState } from "react";

import { BatchOperationsBar } from "../../components/BatchOperationsBar";
import { DeleteConfirmDialog } from "../../components/DeleteConfirmDialog";
import { Icon } from "../../components/Icon";
import { Notice } from "../../components/Notice";
import { Pagination } from "../../components/Pagination";
import { RecycleRowItem } from "../../features/recycle/components/RecycleRowItem";
import { useRecycleBin } from "../../features/recycle/hooks/useRecycleBin";
import type { RecycleItem } from "../../services/api/recycle";
import { useTranslate } from "../../i18n/useTranslate";
import { errorText } from "../../services/api/client";
import "../../features/recycle/components/recycle.css";

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
        <section className="recycle-page" aria-label={t("nav.trash", "回收站")}>
          <header className="recycle-page-header">
            <div className="recycle-page-title">
              <span className="recycle-page-icon" aria-hidden="true">
                <Icon name="trash" size={24} />
              </span>
              <div>
                <h1>{t("nav.trash", "回收站")}</h1>
                <p>{t("recycle.subtitle", "查看待恢复文件，恢复或永久删除选中的记录。")}</p>
              </div>
            </div>
            <dl className="recycle-summary" aria-label={t("recycle.summary", "回收站摘要")}>
              <div className="recycle-summary-item">
                <dt>{t("recycle.totalItems", "总文件")}</dt>
                <dd>{data?.total ?? 0}</dd>
              </div>
              <div className="recycle-summary-item is-selected">
                <dt>{t("recycle.selectedItems", "已选择")}</dt>
                <dd>{selectedItemIds.size}</dd>
              </div>
            </dl>
          </header>

          <div className="recycle-page-content">
            {loading && (
              <div className="recycle-state recycle-loading" role="status">
                <Icon name="refresh" size={22} />
                <span>{t("loading.recycle", "正在加载回收站...")}</span>
              </div>
            )}
            {error && (
              <div className="recycle-state recycle-error" role="alert">
                <Icon name="close" size={22} />
                <span>{errorText(error) || t("recycle.loadFailed", "回收站加载失败")}</span>
              </div>
            )}
            {!loading && !error && (
              <>
                <div className="recycle-list" aria-live="polite">
                  {viewResults.length === 0 ? (
                    <div className="recycle-state recycle-empty" role="status">
                      <span className="recycle-empty-icon" aria-hidden="true">
                        <Icon name="trash" size={26} />
                      </span>
                      <div>
                        <h2>{t("recycle.emptyTitle", "回收站为空")}</h2>
                        <p>{t("recycle.emptyDescription", "没有等待恢复或永久删除的文件。")}</p>
                      </div>
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
                {data && data.total > 0 && (
                  <Pagination
                    currentPage={page}
                    totalPages={Math.ceil(data.total / pageSize)}
                    totalItems={data.total}
                    onPageChange={(nextPage) => {
                      setSelectedItemIds(new Set());
                      setPage(nextPage);
                    }}
                  />
                )}
              </>
            )}
          </div>
        </section>
      </main>

      {isBatchMode && (
        <div className="recycle-batch-layer">
          <BatchOperationsBar
            selectedCount={selectedItemIds.size}
            onSelectAll={handleSelectAll}
            onInvertSelection={handleInvertSelection}
            onRestore={handleBatchRestore}
            onDelete={() => setConfirmDeleteOpen(true)}
            onCancel={() => setSelectedItemIds(new Set())}
            deleteLabel={t("recycle.deletePermanently", "永久删除")}
          />
        </div>
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
