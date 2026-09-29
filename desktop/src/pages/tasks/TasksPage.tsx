import { useMemo, useState } from "react";

import { Icon } from "../../components/Icon";
import { FileDetailDrawer } from "../../components/FileDetailDrawer";
import { Notice } from "../../components/Notice";
import { Pagination } from "../../components/Pagination";
import { FileViewerOverlay, useFileViewer, resolvePreviewCategory } from "../../features/file-preview";
import { TaskRowItem } from "../../features/tasks/components/TaskRowItem";
import { useTasks } from "../../features/tasks/hooks/useTasks";
import { useTranslate } from "../../i18n/useTranslate";
import { errorText } from "../../services/api/client";
import type { FileItem } from "../../services/api/search";
import type { TaskStatus } from "../../services/api/tasks";

import "../../features/tasks/components/tasks.css";

const STATUS_FILTERS: Array<TaskStatus | null> = [null, "queued", "processing", "completed", "failed", "cancelled"];

export function TasksPage() {
  const t = useTranslate();
  const [notice, setNotice] = useState("");
  const [statusFilter, setStatusFilter] = useState<TaskStatus | null>(null);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [retryingAll, setRetryingAll] = useState(false);
  const { data, loading, error, page, setPage, pageSize, reload, retryTask, cancelTask, removeTask } = useTasks(statusFilter);
  const fileViewer = useFileViewer();

  const viewResults = useMemo(() => data?.tasks ?? [], [data]);
  const failedTasks = useMemo(() => viewResults.filter((task) => task.status === "failed"), [viewResults]);
  const selectedTask = useMemo(
    () => viewResults.find((task) => task.id === selectedTaskId) ?? null,
    [selectedTaskId, viewResults],
  );
  const selectedFile = useMemo<FileItem | null>(() => {
    if (!selectedTask) return null;
    return {
      file_id: selectedTask.file.id,
      file_name: selectedTask.file.name,
      file_type: selectedTask.file.file_type,
      category: resolvePreviewCategory(selectedTask.file.file_type),
      path: selectedTask.file.path,
      size: selectedTask.file.size,
      modified: selectedTask.file.modified,
      tags: [],
      score: 0,
      metadata: null,
      chunks: null,
    };
  }, [selectedTask]);

  const handleRetry = async (taskId: string) => {
    const response = await retryTask.mutateAsync(taskId);
    if (response.status === "success") {
      setNotice(t("tasks.retrySuccess", "任务重试已提交"));
      void reload();
    } else {
      setNotice(errorText(response.error) || t("tasks.retryFailed", "重试失败"));
    }
  };

  const handleRemove = async (taskId: string) => {
    const response = await removeTask.mutateAsync(taskId);
    if (response.status === "success") {
      setNotice(t("tasks.removeSuccess", "任务已移除"));
      void reload();
    } else {
      setNotice(errorText(response.error) || t("tasks.removeFailed", "移除任务失败"));
    }
  };

  const handleCancel = async (taskId: string) => {
    const response = await cancelTask.mutateAsync(taskId);
    if (response.status === "success") {
      setNotice(t("tasks.cancelSuccess", "任务终止请求已提交"));
      void reload();
    } else {
      setNotice(errorText(response.error) || t("tasks.cancelFailed", "终止任务失败"));
    }
  };

  const handleRetryAll = async () => {
    if (failedTasks.length === 0) return;
    setRetryingAll(true);
    try {
      const results = await Promise.allSettled(
        failedTasks.map((task) => retryTask.mutateAsync(task.id)),
      );
      const responses = results
        .filter((result): result is PromiseFulfilledResult<Awaited<ReturnType<typeof retryTask.mutateAsync>>> =>
          result.status === "fulfilled")
        .map((result) => result.value);
      const successCount = responses.filter((response) => response.status === "success").length;
      if (successCount > 0) {
        setNotice(`${t("tasks.retryAllSuccess", "已提交")} ${successCount} ${t("tasks.retryUnit", "个重试")}`);
        void reload();
      } else {
        setNotice(errorText(responses[0]?.error) || t("tasks.retryFailed", "重试失败"));
      }
    } finally {
      setRetryingAll(false);
    }
  };

  const handleFilterChange = (status: TaskStatus | null) => {
    setStatusFilter(status);
    setPage(1);
    setSelectedTaskId(null);
    setSidebarOpen(false);
  };

  const handleOpenDetails = (taskId: string) => {
    setSelectedTaskId(taskId);
    setSidebarOpen(true);
  };

  const handleCloseDetails = () => {
    setSidebarOpen(false);
    setSelectedTaskId(null);
  };

  const handleOpenFile = (file: FileItem) => {
    fileViewer.openFile({
      fileId: file.file_id,
      fileName: file.file_name,
      fileType: resolvePreviewCategory(file.file_type),
    });
  };

  const filterLabel = (status: TaskStatus | null) => {
    if (status === null) return t("tasks.all", "全部");
    const labels: Record<TaskStatus, string> = {
      queued: t("tasks.statusQueued", "等待中"),
      processing: t("tasks.statusProcessing", "处理中"),
      completed: t("tasks.statusCompleted", "已完成"),
      failed: t("tasks.statusFailed", "失败"),
      cancelled: t("tasks.statusCancelled", "已终止"),
    };
    return labels[status];
  };

  const filterCount = (status: TaskStatus | null) => {
    if (!data) return 0;
    return status === null ? data.total : data.counts[status] ?? 0;
  };

  return (
    <>
      <main className="main-content">
        <section className="search-results-screen tasks-page" aria-label={t("nav.tasks", "任务队列")}>
          <header className="tasks-page-header">
            <div className="tasks-page-title">
              <span className="tasks-page-icon" aria-hidden="true">
                <Icon name="pulse" size={24} />
              </span>
              <div>
                <h1>{t("nav.tasks", "任务队列")}</h1>
                <p>{t("tasks.subtitle", "查看文件处理进度，并快速处理失败任务。")}</p>
              </div>
            </div>
            <dl className="task-summary" aria-label={t("tasks.summary", "任务状态摘要")}>
              <div className="task-summary-item">
                <dt>{t("tasks.total", "总数")}</dt>
                <dd>{filterCount(null)}</dd>
              </div>
              <div className="task-summary-item is-processing">
                <dt>{t("tasks.statusProcessing", "处理中")}</dt>
                <dd>{filterCount("processing")}</dd>
              </div>
              <div className="task-summary-item is-failed">
                <dt>{t("tasks.statusFailed", "失败")}</dt>
                <dd>{filterCount("failed")}</dd>
              </div>
            </dl>
          </header>

          <div className="task-toolbar">
            <div className="task-filters" role="group" aria-label={t("tasks.statusFilter", "任务状态筛选")}>
              {STATUS_FILTERS.map((status) => (
                <button
                  key={status ?? "all"}
                  type="button"
                  className={`task-filter ${statusFilter === status ? "is-active" : ""}`}
                  aria-pressed={statusFilter === status}
                  onClick={() => handleFilterChange(status)}
                >
                  <span>{filterLabel(status)}</span>
                  <span className="task-filter-count">{filterCount(status)}</span>
                </button>
              ))}
            </div>
            <button
              type="button"
              className="task-retry-all"
              onClick={handleRetryAll}
              disabled={retryingAll || failedTasks.length === 0}
            >
              <Icon name="refresh" size={16} />
              <span>{t("tasks.retryAll", "一键重试")}</span>
              <span className="task-retry-count">{failedTasks.length}</span>
            </button>
          </div>

          <div className={`results-content-split ${sidebarOpen && selectedFile ? "sidebar-expanded" : "sidebar-collapsed"}`}>
            <div className="result-list-container">
              {loading && (
                <div className="task-skeleton-list" role="status" aria-label={t("loading.tasks", "加载中...")}>
                  {[0, 1, 2, 3, 4].map((index) => (
                    <div className="task-skeleton-row" key={index}>
                      <div className="task-skeleton-title" />
                      <div className="task-skeleton-progress" />
                    </div>
                  ))}
                </div>
              )}
              {error && (
                <div className="results-error task-error-state" role="alert">
                  <Icon name="pulse" size={20} />
                  <span>{error}</span>
                </div>
              )}
              {!loading && !error && (
                <div className="result-list" aria-live="polite">
                  {viewResults.length === 0 ? (
                    <div className="task-empty">
                      <span className="task-empty-icon" aria-hidden="true">
                        <Icon name="pulse" size={26} />
                      </span>
                      <h2>{t("tasks.emptyTitle", "没有符合条件的任务")}</h2>
                      <p>{t("tasks.emptyHint", "切换状态筛选，或返回文件库创建新的处理任务。")}</p>
                    </div>
                  ) : (
                    viewResults.map((task) => (
                      <TaskRowItem
                        key={task.id}
                        task={task}
                        onRetry={handleRetry}
                        onCancel={handleCancel}
                        onRemove={handleRemove}
                        onOpenDetails={(selected) => handleOpenDetails(selected.id)}
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
                  onPageChange={setPage}
                  variant="search"
                />
              )}
              <FileDetailDrawer
                isOpen={sidebarOpen}
                onClose={handleCloseDetails}
                file={selectedFile}
                onOpenAction={handleOpenFile}
              />
            </div>
          </div>
        </section>
      </main>

      <FileViewerOverlay
        isOpen={fileViewer.isOpen}
        item={fileViewer.item}
        onClose={fileViewer.onClose}
      />

      {notice && <Notice message={notice} onClose={() => setNotice("")} />}
    </>
  );
}
