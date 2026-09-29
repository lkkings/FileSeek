import { Icon } from "../../../components/Icon";
import { useTranslate } from "../../../i18n/useTranslate";
import { useSystemIntegration } from "../hooks/useSystemIntegration";
import "./settings.css";

export function SystemIntegrationCard() {
  const t = useTranslate();
  const { status, loading, error, setSilentStartup, setFileManagerIntegration } =
    useSystemIntegration();

  return (
    <section
      className="settings-card settings-system-integration-card"
      aria-labelledby="system-integration-title"
    >
      <div className="settings-card-header">
        <div className="settings-card-heading">
          <span className="settings-card-icon">
            <Icon name="settings" size={19} />
          </span>
          <div>
            <h2 id="system-integration-title">
              {t("settings.systemIntegrationTitle", "系统集成")}
            </h2>
            <p>
              {t(
                "settings.systemIntegrationDescription",
                "管理 FileSeek 与操作系统的集成方式",
              )}
            </p>
          </div>
        </div>
      </div>

      <div className="settings-system-integration-list">
        <div className="settings-integration-row">
          <div>
            <h3>{t("settings.silentStartup", "开机静默启动")}</h3>
            <p>
              {t(
                "settings.silentStartupDescription",
                "登录后保持托盘运行，不显示主窗口",
              )}
            </p>
          </div>
          <button
            type="button"
            role="switch"
            aria-checked={status.silentStartupEnabled}
            aria-label={t("settings.silentStartup", "开机静默启动")}
            disabled={loading || setSilentStartup.isPending}
            className={`settings-integration-switch${
              status.silentStartupEnabled ? " is-on" : ""
            }`}
            onClick={() => setSilentStartup.mutate(!status.silentStartupEnabled)}
          >
            <span className="settings-integration-switch-knob" />
          </button>
        </div>

        <div className="settings-integration-row">
          <div>
            <h3>{t("settings.fileManagerIntegration", "文件管理器右键菜单")}</h3>
            <p>
              {t(
                "settings.fileManagerIntegrationDescription",
                "在支持的第一层右键菜单中显示“添加到 FileSeek”",
              )}
            </p>
          </div>
          <button
            type="button"
            role="switch"
            aria-checked={status.fileManagerIntegrationEnabled}
            aria-label={t("settings.fileManagerIntegration", "文件管理器右键菜单")}
            disabled={
              loading ||
              setFileManagerIntegration.isPending ||
              !status.fileManagerIntegrationSupported
            }
            className={`settings-integration-switch${
              status.fileManagerIntegrationEnabled ? " is-on" : ""
            }`}
            onClick={() =>
              setFileManagerIntegration.mutate(!status.fileManagerIntegrationEnabled)
            }
          >
            <span className="settings-integration-switch-knob" />
          </button>
        </div>
      </div>

      {loading && <p className="settings-empty">{t("settings.loading", "正在读取设置...")}</p>}
      {status.finderExtensionApprovalRequired && (
        <p className="settings-inline-error">
          {t(
            "settings.finderApprovalRequired",
            "请在 macOS 系统设置 → 登录项与扩展 → FileSeek 中启用 Finder 扩展",
          )}
        </p>
      )}
      {error && <p className="settings-inline-error">{error}</p>}
      {(setSilentStartup.error || setFileManagerIntegration.error) && (
        <p className="settings-inline-error">
          {setSilentStartup.error instanceof Error
            ? setSilentStartup.error.message
            : setFileManagerIntegration.error instanceof Error
              ? setFileManagerIntegration.error.message
              : t("settings.systemIntegrationSaveFailed", "系统集成设置保存失败")}
        </p>
      )}
    </section>
  );
}
