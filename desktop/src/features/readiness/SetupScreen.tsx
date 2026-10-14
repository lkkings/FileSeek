import { useTranslate } from "../../i18n/useTranslate";
import { hideToTray, type Readiness, type ReadinessState } from "../../services/tauri/readiness";
import { etaSeconds, formatBytes, percent } from "./format";
import { ReadinessProblem } from "./ReadinessProblem";

const INSTALL_STEPS: ReadinessState[] = ["space_check", "downloading", "verifying", "installing", "starting"];

type StepStatus = "done" | "active" | "failed" | "pending";

function stepStatus(step: ReadinessState, readiness: Readiness): StepStatus {
  const current = readiness.state === "failed" ? readiness.failedStep : readiness.state;
  const currentIndex = INSTALL_STEPS.indexOf(current ?? "space_check");
  const index = INSTALL_STEPS.indexOf(step);
  if (readiness.state === "repair_needed") return index < INSTALL_STEPS.length - 1 ? "done" : "failed";
  if (index < currentIndex) return "done";
  if (index > currentIndex) return "pending";
  return readiness.state === "failed" ? "failed" : "active";
}

function formatEta(seconds: number, t: ReturnType<typeof useTranslate>): string {
  if (seconds < 60) return t("readiness.etaSeconds", "约 {n} 秒", { n: seconds });
  if (seconds < 3600) return t("readiness.etaMinutes", "约 {n} 分钟", { n: Math.ceil(seconds / 60) });
  return t("readiness.etaHours", "约 {n} 小时", { n: (seconds / 3600).toFixed(1) });
}

/**
 * Shown instead of the library until the backend first becomes ready: the honest version
 * of "starting", because without the model there is nothing to use yet.
 */
export function SetupScreen({ readiness, installing }: { readiness: Readiness | null; installing: boolean }) {
  const t = useTranslate();
  const labels: Record<string, string> = {
    space_check: t("readiness.stepSpaceCheck", "检查磁盘空间"),
    downloading: t("readiness.stepDownloading", "下载模型"),
    verifying: t("readiness.stepVerifying", "校验文件"),
    installing: t("readiness.stepInstalling", "安装模型"),
    starting: t("readiness.stepStarting", "启动服务"),
  };
  const statusText: Record<StepStatus, string> = {
    done: t("readiness.statusDone", "已完成"),
    active: t("readiness.statusActive", "进行中"),
    failed: t("readiness.statusFailed", "失败"),
    pending: t("readiness.statusPending", "等待中"),
  };
  const showProgress = readiness && readiness.total > 0 && ["downloading", "verifying", "installing"].includes(readiness.state);
  const eta = readiness ? etaSeconds(readiness.done, readiness.total, readiness.bytesPerSecond) : null;
  const problem = readiness && (readiness.state === "failed" || readiness.state === "repair_needed");

  return (
    <main className="readiness-setup" aria-labelledby="readiness-setup-title">
      <div className="readiness-setup-card">
        <h1 id="readiness-setup-title">
          {installing ? t("readiness.titleInstalling", "正在准备 FileSeek") : t("readiness.titleStarting", "正在启动 FileSeek")}
        </h1>
        {installing && (
          <p className="readiness-setup-lead">
            {t("readiness.lead", "首次使用需要下载搜索所需的模型（约 890 MB），完成后不再需要。")}
          </p>
        )}

        {installing ? (
          <ol className="readiness-steps">
            {INSTALL_STEPS.map((step) => {
              const status = readiness ? stepStatus(step, readiness) : "pending";
              return (
                <li key={step} className={`readiness-step is-${status}`} aria-current={status === "active" ? "step" : undefined}>
                  <span className="readiness-step-mark" aria-hidden="true" />
                  <span className="readiness-step-label">{labels[step]}</span>
                  <span className="readiness-visually-hidden">{statusText[status]}</span>
                </li>
              );
            })}
          </ol>
        ) : (
          !problem && <p className="readiness-setup-lead" role="status">{t("readiness.starting", "正在启动服务…")}</p>
        )}

        {showProgress && readiness && (
          <div className="readiness-progress">
            <div
              className="readiness-progress-bar"
              role="progressbar"
              aria-label={labels[readiness.state]}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={percent(readiness.done, readiness.total)}
            >
              <span style={{ width: `${percent(readiness.done, readiness.total)}%` }} />
            </div>
            <p className="readiness-progress-text">
              {formatBytes(readiness.done)} / {formatBytes(readiness.total)}
              {readiness.state === "downloading" && readiness.bytesPerSecond > 0 && (
                <> · {formatBytes(readiness.bytesPerSecond)}/s</>
              )}
              {readiness.state === "downloading" && eta !== null && <> · {formatEta(eta, t)}</>}
            </p>
          </div>
        )}

        {problem && readiness && <ReadinessProblem readiness={readiness} />}

        {installing && !problem && (
          <button type="button" className="readiness-button" onClick={() => void hideToTray()}>
            {t("readiness.hideToTray", "最小化到托盘，完成后通知我")}
          </button>
        )}
      </div>
    </main>
  );
}
