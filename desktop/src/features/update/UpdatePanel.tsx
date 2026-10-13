import { useTranslate } from "../../i18n/useTranslate";
import {
  cancelUpdateDownload,
  checkForUpdates,
  downloadUpdate,
  installUpdate,
  type UpdateStatus,
} from "../../services/tauri/update";
import { formatBytes, percent } from "../readiness/format";
import { useUpdateStatus } from "./useUpdateStatus";
import "./update.css";

type Translate = ReturnType<typeof useTranslate>;

function phaseText(status: UpdateStatus, t: Translate): string {
  const version = status.update?.version ?? "";
  switch (status.phase) {
    case "disabled":
      return t("update.disabled", "此版本不检查更新。");
    case "checking":
      return t("update.checking", "正在检查更新…");
    case "up_to_date":
      return t("update.upToDate", "已是最新版本。");
    case "available":
      return t("update.available", "有新版本 {version} 可用。", { version });
    case "downloading":
      return t("update.downloading", "正在下载 {version}…", { version });
    case "ready":
      return t("update.ready", "更新已就绪，重启以完成更新。");
    case "failed":
      return t("update.failed", "更新失败：{error}", { error: status.error ?? "" });
    case "idle":
    default:
      return status.error
        ? t("update.checkFailed", "检查更新失败，稍后会自动重试。")
        : t("update.idle", "尚未检查更新。");
  }
}

/** The actions that fit the current phase: shared by the settings card and the banner. */
export function UpdateActions({ status, onStatus }: { status: UpdateStatus; onStatus: (s: UpdateStatus) => void }) {
  const t = useTranslate();
  switch (status.phase) {
    case "available":
    case "failed":
      return status.update ? (
        <button type="button" className="update-button is-primary" onClick={() => void downloadUpdate()}>
          {status.phase === "failed" ? t("update.retry", "重试") : t("update.download", "下载更新")}
        </button>
      ) : null;
    case "downloading":
      return (
        <button type="button" className="update-button" onClick={() => void cancelUpdateDownload()}>
          {t("update.cancel", "取消")}
        </button>
      );
    case "ready":
      return (
        <button type="button" className="update-button is-primary" onClick={() => void installUpdate()}>
          {t("update.restart", "重启并更新")}
        </button>
      );
    case "disabled":
      return null;
    default:
      return (
        <button
          type="button"
          className="update-button"
          disabled={status.phase === "checking"}
          onClick={() => void checkForUpdates().then(onStatus).catch(() => {})}
        >
          {t("update.check", "检查更新")}
        </button>
      );
  }
}

export function UpdateProgress({ status }: { status: UpdateStatus }) {
  if (status.phase !== "downloading" || !status.total) return null;
  const value = percent(status.done, status.total);
  return (
    <div className="update-progress">
      <div className="update-progress-bar" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={value}>
        <span style={{ width: `${value}%` }} />
      </div>
      <span>
        {formatBytes(status.done)} / {formatBytes(status.total)}
      </span>
    </div>
  );
}

/** Settings → Updates: current version, what is available, and the one next step. */
export function UpdateCard() {
  const t = useTranslate();
  const [status, setStatus] = useUpdateStatus();

  return (
    <section className="settings-card update-card" aria-labelledby="update-card-title">
      <div className="settings-card-header">
        <div className="settings-card-heading">
          <div>
            <h2 id="update-card-title">{t("update.title", "应用更新")}</h2>
            <p>{t("update.current", "当前版本 {version}", { version: status.currentVersion })}</p>
          </div>
        </div>
      </div>
      <p className="update-status" role="status">
        {phaseText(status, t)}
      </p>
      {status.update?.notes && <p className="update-notes">{status.update.notes}</p>}
      <UpdateProgress status={status} />
      <div className="update-actions">
        <UpdateActions status={status} onStatus={setStatus} />
      </div>
    </section>
  );
}
