import { useMemo, useState } from "react";

import { Notice } from "../../components/Notice";
import { Pagination } from "../../components/Pagination";
import { TaskRowItem } from "../../features/tasks/components/TaskRowItem";
import { useTasks } from "../../features/tasks/hooks/useTasks";
import { useTranslate } from "../../i18n/useTranslate";
import type { TaskStatus } from "../../services/api/tasks";
import { errorText } from "../../services/api/client";

const STATUS_FILTERS: Array<TaskStatus | null> = [null, "queued", "processing", "completed", "failed"];

export function TasksPage() {
  const t = useTranslate();
  const [notice, setNotice] = useState("");
  const [statusFilter, setStatusFilter] = useState<TaskStatus | null>(null);
  const { data, loading, error, page, setPage, pageSize, reload, retryTask } = useTasks(statusFilter);

  const viewResults = useMemo(() => data?.tasks ?? [], [data]);

  const handleRetry = async (taskId: string) => {
    const response = await retryTask.mutateAsync(taskId);
    if (response.status === "success") {
      setNotice(t("tasks.retrySuccess", "任务重试已提交"));
      void reload();
    } else {
      setNotice(errorText(response.error) || t("tasks.retryFailed", "重试失败"));
    }
  };

  const filterLabel = (status: TaskStatus | null) => {
    if (status === null) return t("tasks.all", "全部");
    const labels: Record<TaskStatus, string> = {
      queued: t("tasks.statusQueued", "等待中"),
      processing: t("tasks.statusProcessing", "处理中"),
      completed: t("tasks.statusCompleted", "已完成"),
      failed: t("tasks.statusFailed", "失败"),
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
        <section className="search-results-screen" aria-label={t("nav.tasks", "任务队列")}>
          <div className="results-heading task-results-heading">
            <div className="results-title-group">
              <p>
                <strong>{t("nav.tasks", "任务队列")}</strong>
              </p>
            </div>
            <div className="task-filters" role="group" aria-label={t("tasks.statusFilter", "任务状态筛选")}>
              {STATUS_FILTERS.map((status) => (
                <button
                  key={status ?? "all"}
                  type="button"
                  className={`sidebar-action-btn ${statusFilter === status ? "btn-primary" : ""}`}
                  onClick={() => {
                    setStatusFilter(status);
                    setPage(1);
                  }}
                >
                  {filterLabel(status)}
                  <span className="task-filter-count">{filterCount(status)}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="results-content-split sidebar-collapsed">
            <div className="result-list-container">
              {loading && <div className="results-loading">{t("loading.tasks", "加载中...")}</div>}
              {error && <div className="results-error">{error}</div>}
              {!loading && !error && (
                <div className="result-list" aria-live="polite">
                  {viewResults.length === 0 ? (
                    <div className="empty-results">
                      <p>{t("tasks.empty", "暂无任务")}</p>
                    </div>
                  ) : (
                    viewResults.map((task) => (
                      <TaskRowItem key={task.id} task={task} onRetry={handleRetry} />
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
            </div>
          </div>
        </section>
      </main>

      {notice && <Notice message={notice} onClose={() => setNotice("")} />}
    </>
  );
}
