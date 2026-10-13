import { useState } from "react";

import { useTranslate } from "../../i18n/useTranslate";
import { markSetupPromptShown } from "../../services/preferences";
import { useSystemIntegration } from "../settings/hooks/useSystemIntegration";

/**
 * Offered once, the first time the app is ready. Everything starts unchecked: the user
 * opts in, and the same switches stay available under Settings → System integration.
 */
export function SuggestedSettingsDialog({ onClose }: { onClose: () => void }) {
  const t = useTranslate();
  const { status, setSilentStartup, setFileManagerIntegration } = useSystemIntegration();
  const [startup, setStartup] = useState(false);
  const [contextMenu, setContextMenu] = useState(false);
  const [saving, setSaving] = useState(false);

  function close() {
    markSetupPromptShown();
    onClose();
  }

  async function apply() {
    setSaving(true);
    try {
      if (startup) await setSilentStartup.mutateAsync(true);
      if (contextMenu) await setFileManagerIntegration.mutateAsync(true);
    } catch {
      // Whatever failed can be retried from Settings; the dialog is not the only way in.
    } finally {
      setSaving(false);
      close();
    }
  }

  return (
    <div className="readiness-dialog-backdrop">
      <div className="readiness-dialog" role="dialog" aria-modal="true" aria-labelledby="suggested-settings-title">
        <h2 id="suggested-settings-title">{t("readiness.suggestedTitle", "建议设置")}</h2>
        <p>{t("readiness.suggestedLead", "以下选项都可以稍后在“系统设置 → 系统集成”中修改。")}</p>
        <label className="readiness-dialog-option">
          <input type="checkbox" checked={startup} onChange={(event) => setStartup(event.target.checked)} />
          <span>{t("settings.silentStartup", "开机静默启动")}</span>
        </label>
        {status.fileManagerIntegrationSupported && (
          <label className="readiness-dialog-option">
            <input type="checkbox" checked={contextMenu} onChange={(event) => setContextMenu(event.target.checked)} />
            <span>{t("settings.fileManagerIntegration", "文件管理器右键菜单")}</span>
          </label>
        )}
        <div className="readiness-dialog-actions">
          <button type="button" className="readiness-button" disabled={saving} onClick={close}>
            {t("readiness.suggestedSkip", "跳过")}
          </button>
          <button type="button" className="readiness-button is-primary" disabled={saving} onClick={() => void apply()}>
            {t("readiness.suggestedApply", "完成")}
          </button>
        </div>
      </div>
    </div>
  );
}
