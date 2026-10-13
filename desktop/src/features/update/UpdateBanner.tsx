import { useState } from "react";

import { useTranslate } from "../../i18n/useTranslate";
import { UpdateActions, UpdateProgress } from "./UpdatePanel";
import { useUpdateStatus } from "./useUpdateStatus";
import "./update.css";

const DISMISSED_KEY = "fileseek.updateDismissed.v1";

function loadDismissed(): string | null {
  try {
    return window.localStorage.getItem(DISMISSED_KEY);
  } catch {
    return null;
  }
}

function saveDismissed(version: string) {
  try {
    window.localStorage.setItem(DISMISSED_KEY, version);
  } catch {
    return;
  }
}

/**
 * How loudly to say an update exists:
 * - required (this version is below Keygate's minimum supported version): a banner that
 *   cannot be closed until the update is installed, with Keygate's message
 * - otherwise: once per version, with "later"; Settings shows it too
 * Neither disables anything. A download in progress or waiting for a restart always shows,
 * so the user can finish what they started.
 */
export function UpdateBanner() {
  const t = useTranslate();
  const [status, setStatus] = useUpdateStatus();
  const [dismissed, setDismissed] = useState<string | null>(loadDismissed);
  const update = status.update;
  if (!update) return null;

  const busy = ["downloading", "ready"].includes(status.phase);
  const critical = update.required;
  const recommended = dismissed !== update.version;
  if (!busy && !critical && !recommended) return null;
  if (status.phase === "up_to_date" || status.phase === "disabled") return null;

  const message = critical
    ? update.requiredMessage ?? t("update.bannerRequired", "当前版本已不再受支持，请更新到 {version}。", { version: update.version })
    : status.phase === "ready"
      ? t("update.ready", "更新已就绪，重启以完成更新。")
      : t("update.bannerRecommended", "新版本 {version} 可用。", { version: update.version });

  return (
    <div className={`update-banner${critical ? " is-critical" : ""}`} role={critical ? "alert" : "status"}>
      <span>{message}</span>
      <UpdateProgress status={status} />
      <UpdateActions status={status} onStatus={setStatus} />
      {!critical && !busy && (
        <button
          type="button"
          className="update-button"
          onClick={() => {
            saveDismissed(update.version);
            setDismissed(update.version);
          }}
        >
          {t("update.later", "稍后")}
        </button>
      )}
    </div>
  );
}
