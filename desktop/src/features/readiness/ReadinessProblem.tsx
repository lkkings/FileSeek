import { useState } from "react";

import { useTranslate } from "../../i18n/useTranslate";
import { repairRuntime, retryReadiness, type Readiness } from "../../services/tauri/readiness";
import { formatBytes } from "./format";

type Translate = ReturnType<typeof useTranslate>;

function problemMessage(readiness: Readiness, t: Translate): string {
  if (readiness.state === "repair_needed") {
    return t("readiness.repairPrompt", "后端无法启动，是否修复运行时？修复会重新下载运行时，不影响文件库。");
  }
  switch (readiness.errorKind) {
    case "network":
      return t("readiness.errorNetwork", "网络连接失败。网络恢复后点击重试，会从断点继续下载。");
    case "integrity":
      return t("readiness.errorIntegrity", "下载的文件校验失败，已丢弃。请重试。");
    case "disk_space":
      return readiness.space
        ? t("readiness.errorDiskSpace", "磁盘空间不足：需要 {required}，{path} 所在磁盘只有 {available} 可用。", {
            required: formatBytes(readiness.space.required),
            available: formatBytes(readiness.space.available),
            path: readiness.space.path,
          })
        : t("readiness.errorDiskSpaceShort", "磁盘空间不足。");
    case "unwritable":
      return t("readiness.errorUnwritable", "无法写入 {path}，请检查该目录的权限。", {
        path: readiness.unwritablePath ?? "",
      });
    case "install":
      return t("readiness.errorInstall", "安装运行时失败。请重试。");
    case "unsupported":
      return t("readiness.errorUnsupported", "当前平台暂不支持。");
    case "backend":
    default:
      return t("readiness.errorBackend", "后端服务无法启动。");
  }
}

/** What went wrong and what the user can do about it: retry, or repair after a crash loop. */
export function ReadinessProblem({ readiness }: { readiness: Readiness }) {
  const t = useTranslate();
  const [confirmingRepair, setConfirmingRepair] = useState(false);
  const [busy, setBusy] = useState(false);
  const repairable = readiness.state === "repair_needed";
  const retryable = readiness.state === "failed" && readiness.errorKind !== "unsupported";

  async function run(action: () => Promise<void>) {
    setBusy(true);
    try {
      await action();
    } finally {
      setBusy(false);
      setConfirmingRepair(false);
    }
  }

  return (
    <div className="readiness-problem" role="alert">
      <p className="readiness-problem-message">{problemMessage(readiness, t)}</p>
      {readiness.error && (
        <details className="readiness-problem-details">
          <summary>{t("readiness.details", "详细信息")}</summary>
          <pre>{readiness.error}</pre>
        </details>
      )}
      {readiness.logPath && (
        <p className="readiness-problem-log">
          {t("readiness.logPath", "日志：")}
          <code>{readiness.logPath}</code>
        </p>
      )}
      <div className="readiness-problem-actions">
        {retryable && (
          <button type="button" className="readiness-button is-primary" disabled={busy} onClick={() => void run(retryReadiness)}>
            {t("readiness.retry", "重试")}
          </button>
        )}
        {repairable && !confirmingRepair && (
          <button type="button" className="readiness-button is-primary" disabled={busy} onClick={() => setConfirmingRepair(true)}>
            {t("readiness.repair", "修复运行时")}
          </button>
        )}
        {repairable && confirmingRepair && (
          <>
            <span className="readiness-problem-confirm">
              {t("readiness.repairConfirm", "将删除并重新下载运行时，确定吗？")}
            </span>
            <button type="button" className="readiness-button is-primary" disabled={busy} onClick={() => void run(repairRuntime)}>
              {t("readiness.repairConfirmYes", "确定修复")}
            </button>
            <button type="button" className="readiness-button" disabled={busy} onClick={() => setConfirmingRepair(false)}>
              {t("common.cancel", "取消")}
            </button>
          </>
        )}
      </div>
    </div>
  );
}
