import { Icon } from "../../../components/Icon";
import { useTranslate } from "../../../i18n/useTranslate";
import type { TaskItem, TaskStage, TaskStatus } from "../../../services/api/tasks";
import "../../file-search/components/search-results.css";
import "./tasks.css";

interface TaskRowItemProps {
  task: TaskItem;
  onRetry: (taskId: string) => void;
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

function formatDate(value: string) {
  if (!value.includes("T")) return value;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const pad = (part: number) => part.toString().padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export function TaskRowItem({ task, onRetry, onRemove, onOpenDetails }: TaskRowItemProps) {
  const t = useTranslate();
  const progress = Math.min(100, Math.max(0, task.progress));

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
            <h2>{task.file.name}</h2>
            <p className="result-path">{task.file.path}</p>
            <p className="task-row-meta">
              <Icon name="clock" size={14} />
              <span>{formatDate(task.created_at)}</span>
              <span className={`task-status task-status-${task.status}`}>
                {statusLabel(task.status, t)}
              </span>
            </p>
          </div>
        </div>

        <div className="task-row-progress">
          <div className="task-progress-header">
            <span>{t("tasks.progress", "进度")}</span>
            <strong>{progress}%</strong>
          </div>
          <div
            className="task-progress-track"
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={progress}
            aria-label={`${task.file.name} ${t("tasks.progress", "进度")}`}
          >
            <div className="task-progress-fill" style={{ width: `${progress}%` }} />
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
        {task.status === "failed" && (
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
