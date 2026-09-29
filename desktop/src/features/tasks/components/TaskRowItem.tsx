import { Icon } from "../../../components/Icon";
import { useTranslate } from "../../../i18n/useTranslate";
import { formatDateTime } from "../../../i18n/formatDateTime";
import type { TaskItem, TaskStage, TaskStatus } from "../../../services/api/tasks";
import "../../file-search/components/search-results.css";
import "./tasks.css";

interface TaskRowItemProps {
  task: TaskItem;
  onRetry: (taskId: string) => void;
  onCancel: (taskId: string) => void;
  onRemove: (taskId: string) => void;
  onOpenDetails: (task: TaskItem) => void;
}

const TASK_STAGES: TaskStage[] = ["extracted", "encoded", "classify", "indexed"];

function statusLabel(status: TaskStatus, t: ReturnType<typeof useTranslate>) {
  const labels: Record<TaskStatus, string> = {
    queued: t("tasks.statusQueued", "等待中"),
    processing: t("tasks.statusProcessing", "处理中"),
    completed: t("tasks.statusCompleted", "已完成"),
    failed: t("tasks.statusFailed", "失败"),
    cancelled: t("tasks.statusCancelled", "已终止"),
  };
  return labels[status];
}

function stageLabel(stage: TaskStage, t: ReturnType<typeof useTranslate>) {
  const labels: Record<TaskStage, string> = {
    extracted: t("tasks.stageExtracted", "提取"),
    encoded: t("tasks.stageEncoded", "编码"),
    classify: t("tasks.stageClassify", "分类"),
    indexed: t("tasks.stageIndexed", "构建索引"),
  };
  return labels[stage];
}

export function TaskRowItem({ task, onRetry, onCancel, onRemove, onOpenDetails }: TaskRowItemProps) {
  const t = useTranslate();
  const hasCountPair =
    task.completed_count !== null &&
    task.total_count !== null &&
    task.total_count > 0 &&
    task.completed_count >= 0 &&
    task.completed_count <= task.total_count;
  const totalCount = hasCountPair ? (task.total_count as number) : 0;
  const completedCount = hasCountPair ? (task.completed_count as number) : 0;
  const progressText = hasCountPair
    ? `${completedCount}/${totalCount}`
    : statusLabel(task.status, t);
  const progressPercent = hasCountPair
    ? (completedCount / totalCount) * 100
    : 0;

  return (
    <article className={`result-row task-row status-${task.status}`}>
      <button
        className="task-row-select"
        type="button"
        onClick={() => onOpenDetails(task)}
        aria-label={`${task.file.name} ${t("search.details", "文件详情")}`}
      >
        <div className="task-row-main">
          <div className={`file-type-icon file-type-${task.file.file_type.toLowerCase()}`} aria-hidden="true">
            {task.file.file_type}
          </div>
          <div className="task-row-copy">
            <div className="task-row-title-row">
              <h2>{task.file.name}</h2>
              <span className={`task-status task-status-${task.status}`}>
                {statusLabel(task.status, t)}
              </span>
            </div>
            <p className="result-path">{task.file.path}</p>
            <p className="task-row-meta">
              <Icon name="clock" size={14} />
              <span>{formatDateTime(task.created_at)}</span>
            </p>
          </div>
        </div>

        <div className="task-row-progress">
          <div className="task-progress-header">
            <span>{t("tasks.progress", "进度")}</span>
            <strong>{progressText}</strong>
          </div>
          <div
            className={[
              "task-progress-track",
              !hasCountPair && task.status === "processing" ? "is-indeterminate" : "",
            ].join(" ")}
            role={hasCountPair ? "progressbar" : undefined}
            aria-valuemin={hasCountPair ? 0 : undefined}
            aria-valuemax={hasCountPair ? totalCount : undefined}
            aria-valuenow={hasCountPair ? completedCount : undefined}
            aria-valuetext={hasCountPair ? progressText : undefined}
            aria-label={hasCountPair ? `${task.file.name} ${t("tasks.progress", "进度")}` : undefined}
          >
            <div className="task-progress-fill" style={{ width: `${progressPercent}%` }} />
          </div>
          <ol className="task-stage-flow" aria-label={`${task.file.name} ${t("tasks.stageFlow", "阶段流程")}`}>
            {TASK_STAGES.map((stage) => {
              const isCurrent = task.stage === stage;
              const stepClass = [
                "task-stage-step",
                isCurrent && task.status === "processing" ? "is-current" : "",
                isCurrent && task.status === "failed" ? "is-failed" : "",
                task.status === "completed" ? "is-complete" : "",
              ]
                .filter(Boolean)
                .join(" ");

              return (
                <li
                  key={stage}
                  className={stepClass}
                  aria-current={isCurrent && task.status === "processing" ? "step" : undefined}
                >
                  <span className="task-stage-dot" aria-hidden="true" />
                  <span className="task-stage-name">{stageLabel(stage, t)}</span>
                </li>
              );
            })}
          </ol>
          {task.error_message && <p className="task-error">{task.error_message}</p>}
        </div>
      </button>

      <div className="task-row-actions">
        {(task.status === "failed" || task.status === "cancelled") && (
          <button
            type="button"
            className="task-retry-button"
            aria-label={`${task.file.name} ${t("tasks.retry", "重试")}`}
            onClick={() => onRetry(task.id)}
          >
            <Icon name="refresh" size={16} />
            <span className="task-retry-label">{t("tasks.retry", "重试")}</span>
          </button>
        )}
        {task.status === "processing" && (
          <button
            type="button"
            className="task-cancel-button"
            aria-label={`${task.file.name} ${t("tasks.cancel", "终止")}`}
            onClick={() => onCancel(task.id)}
          >
            <Icon name="close" size={16} />
            <span className="task-cancel-label">{t("tasks.cancel", "终止")}</span>
          </button>
        )}
        <button
          type="button"
          className="task-remove-button"
          aria-label={`${task.file.name} ${t("tasks.remove", "移除")}`}
          title={task.status === "processing" ? t("tasks.removeProcessingDisabled", "处理中的任务不能移除") : undefined}
          disabled={task.status === "processing"}
          onClick={() => onRemove(task.id)}
        >
          <Icon name="trash" size={16} />
          <span className="task-remove-label">{t("tasks.remove", "移除")}</span>
        </button>
      </div>
    </article>
  );
}
