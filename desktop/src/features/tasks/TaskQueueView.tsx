import { useEffect, useRef, useState, useCallback } from "react";
import { useTranslation, type TranslationKeys } from "../../i18n/useTranslation";
import { defaultClient, type IngestionTask } from "../../api/client";

export function TaskQueueView() {
  const { t } = useTranslation();
  const [tasks, setTasks] = useState<IngestionTask[]>([]);
  const [activeTab, setActiveTab] = useState<"all" | "processing" | "completed" | "failed">("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const requestVersion = useRef(0);

  const fetchTasks = useCallback(async () => {
    const version = ++requestVersion.current;
    setError(null);
    try {
      const filter = activeTab === "all" ? undefined : activeTab;
      const response = await defaultClient.get<{ tasks: IngestionTask[] }>("/tasks");
      if (response.status === "success" && response.data) {
        let list = response.data.tasks;
        if (filter) {
          list = list.filter((t) => t.status === filter);
        }
        if (version === requestVersion.current) setTasks(list);
      } else if (version === requestVersion.current) {
        setError(String(response.error || "无法读取任务队列"));
      }
    } catch (err) {
      if (version === requestVersion.current) {
        setError(err instanceof Error ? err.message : "无法读取任务队列");
      }
    } finally {
      if (version === requestVersion.current) setLoading(false);
    }
  }, [activeTab]);

  useEffect(() => {
    // Defer using microtask to satisfy React setState-in-effect guidelines
    Promise.resolve().then(() => {
      fetchTasks();
    });

    // Listen to updates from InMemoryMockAdapter or poll periodically
    const handleMockUpdate = () => {
      Promise.resolve().then(() => {
        fetchTasks();
      });
    };

    window.addEventListener("mock-tasks-updated", handleMockUpdate);
    const interval = setInterval(fetchTasks, 5000);

    return () => {
      requestVersion.current += 1;
      window.removeEventListener("mock-tasks-updated", handleMockUpdate);
      clearInterval(interval);
    };
  }, [fetchTasks]);

  const handleRetry = async (taskId: string) => {
    try {
      const response = await defaultClient.post<IngestionTask>(`/tasks/${taskId}/retry`);
      if (response.status === "success") {
        fetchTasks();
        // Dispatches global event so that the sidebar badge refreshes too
        window.dispatchEvent(new CustomEvent("mock-tasks-updated"));
      } else {
        alert(response.error || "重试失败");
      }
    } catch (err) {
      const error = err as { message?: string };
      alert("无法提交重试：" + (error.message || "Unknown error"));
    }
  };

  const getStatusClass = (status: string) => {
    switch (status) {
      case "queued": return "task-badge--queued";
      case "processing": return "task-badge--processing";
      case "completed": return "task-badge--completed";
      case "failed": return "task-badge--failed";
      default: return "";
    }
  };

  const getStageLabel = (stage: string | null) => {
    if (!stage) return "";
    switch (stage) {
      case "moved": return t("tasks.stage.moved");
      case "extracted": return t("tasks.stage.extracted");
      case "encoded": return t("tasks.stage.encoded");
      case "indexed": return t("tasks.stage.indexed");
      default: return stage;
    }
  };

  return (
    <div className="task-queue-view">
      <div className="task-queue-view__header">
        {/* Filtering Status tabs */}
        <div className="task-queue-view__tabs" role="tablist">
          <button
            type="button"
            className={`task-tab ${activeTab === "all" ? "task-tab--active" : ""}`}
            onClick={() => setActiveTab("all")}
          >
            {t("search.filterAll")}
          </button>
          <button
            type="button"
            className={`task-tab ${activeTab === "processing" ? "task-tab--active" : ""}`}
            onClick={() => setActiveTab("processing")}
          >
            {t("tasks.status.processing")}
          </button>
          <button
            type="button"
            className={`task-tab ${activeTab === "completed" ? "task-tab--active" : ""}`}
            onClick={() => setActiveTab("completed")}
          >
            {t("tasks.status.completed")}
          </button>
          <button
            type="button"
            className={`task-tab ${activeTab === "failed" ? "task-tab--active" : ""}`}
            onClick={() => setActiveTab("failed")}
          >
            {t("tasks.status.failed")}
          </button>
        </div>
      </div>

      {error ? <div className="library-error-banner" role="alert">{error}</div> : loading && tasks.length === 0 ? (
        <div className="task-queue-view__loading">
          <div className="search-bar__spinner" style={{ margin: "40px auto" }} />
        </div>
      ) : tasks.length === 0 ? (
        <div className="task-queue-view__empty">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" width="48" height="48">
            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
          </svg>
          <p>{t("tasks.noTasks")}</p>
        </div>
      ) : (
        <div className="task-list">
          {tasks.map((task) => (
            <div key={task.id} className="task-item">
              <div className="task-item__main">
                <div className="task-item__info">
                  <div className="task-item__filename">
                    {task.source_path.split("/").pop()}
                  </div>
                  <div className="task-item__path">{task.source_path}</div>
                </div>
                <div className="task-item__status-area">
                  <span className={`task-badge ${getStatusClass(task.status)}`}>
                    {t(`tasks.status.${task.status}` as TranslationKeys)}
                  </span>
                  {task.status === "failed" && (
                    <button
                      type="button"
                      className="theme-btn theme-btn--sm"
                      onClick={() => handleRetry(task.id)}
                    >
                      {t("tasks.retry")}
                    </button>
                  )}
                </div>
              </div>

              {/* Ingestion active progress & stage markers */}
              {task.status === "processing" && (
                <div className="task-item__progress-area">
                  <div className="task-item__progress-bar-bg">
                    <div
                      className="task-item__progress-bar-fill"
                      style={{ width: `${task.progress}%` }}
                    />
                  </div>
                  <div className="task-item__progress-text">
                    <span>{getStageLabel(task.stage)}</span>
                    <span>{t("tasks.progress", { progress: task.progress })}</span>
                  </div>
                </div>
              )}

              {/* Failure error message block */}
              {task.status === "failed" && task.error_message && (
                <div className="task-item__error-desc">
                  {t("tasks.failedReason", { reason: task.error_message })}
                </div>
              )}

              <div className="task-item__footer">
                <span>ID: {task.id}</span>
                <span>{task.created_at}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
export default TaskQueueView;
