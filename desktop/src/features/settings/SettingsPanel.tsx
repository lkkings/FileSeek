import { useEffect, useRef, useState } from "react";
import { useTranslation, Language } from "../../i18n/useTranslation";
import { defaultClient, errorText } from "../../api/client";
import { getTheme, toggleTheme, type Theme } from "../../styles/theme";

export function SettingsPanel() {
  const { t, language, setLanguage } = useTranslation();

  // Settings State
  const [libRoot, setLibRoot] = useState("");
  const [theme, setThemeState] = useState<Theme>(() => getTheme());

  // NAS Config State
  const [nasProtocol, setNasProtocol] = useState("smb");
  const [nasHost, setNasHost] = useState("");
  const [nasShare, setNasShare] = useState("");
  const [nasUser, setNasUser] = useState("");
  const [nasPassword, setNasPassword] = useState("");
  const [nasConnected, setNasConnected] = useState(true);
  
  const [nasTesting, setNasTesting] = useState(false);
  const [nasTestResult, setNasTestResult] = useState<string | null>(null);
  const [settingsError, setSettingsError] = useState<string | null>(null);
  const mounted = useRef(true);

  useEffect(() => {
    // Fetch current settings configuration
    defaultClient.get<{
      lib_root: string;
      nas_enabled: boolean;
    }>("/settings").then((res) => {
      if (!mounted.current) return;
      if (res.status === "success" && res.data) {
        setLibRoot(res.data.lib_root);
        setNasConnected(res.data.nas_enabled);
      }
    }).catch((cause) => {
      if (mounted.current) setSettingsError(cause instanceof Error ? cause.message : "无法读取设置");
    });
    return () => { mounted.current = false; };
  }, []);

  const handleLibRootChange = async (newPath: string) => {
    setLibRoot(newPath);
    // Dynamic validation check
    try {
      const response = await defaultClient.post("/settings", { lib_root: newPath });
      if (response.status === "error") {
        alert(t("settings.libRootError"));
      }
    } catch {
      alert(t("settings.libRootError"));
    }
  };

  const handleToggleTheme = () => {
    const next = toggleTheme();
    setThemeState(next);
  };

  const handleNasTest = async () => {
    setNasTesting(true);
    setNasTestResult(null);
    try {
      // 后端 NASTestRequest 五个字段全必填，少一个就是 422。
      const response = await defaultClient.post<string>("/settings/nas/test", {
        protocol: nasProtocol,
        host: nasHost,
        share_path: nasShare,
        username: nasUser,
        password: nasPassword,
      });

      if (response.status === "success") {
        setNasTestResult("success");
      } else {
        setNasTestResult(errorText(response.error) || "Connection timeout.");
      }
    } catch (err) {
      const error = err as { message?: string };
      setNasTestResult(error.message || "Connection timeout.");
    } finally {
      setNasTesting(false);
    }
  };

  return (
    <div className="settings-panel">
      {settingsError && <div className="library-error-banner" role="alert">{settingsError}</div>}
      <h1 className="settings-panel__title">{t("settings.title")}</h1>

      <div className="settings-sections">
        {/* 1. General Panel */}
        <section className="settings-card">
          <h2 className="settings-card__title">{t("settings.general")}</h2>
          
          <div className="form-group">
            <label>{t("settings.libRoot")}</label>
            <div className="lib-root-input-box">
              <input
                type="text"
                className="theme-input"
                value={libRoot}
                onChange={(e) => handleLibRootChange(e.target.value)}
                placeholder="/Users/username/FileSeekLibrary"
              />
              <button
                type="button"
                className="theme-btn theme-btn--outline"
                onClick={() => handleLibRootChange("/Users/lkkings/FileSeekLibrary_New")}
              >
                {t("settings.libRootSelect")}
              </button>
            </div>
            <p className="form-help-text">{t("settings.libRootDesc")}</p>
          </div>

          <div className="form-group" style={{ marginTop: "20px" }}>
            <label>{t("settings.language")}</label>
            <select
              className="theme-select"
              value={language}
              onChange={(e) => setLanguage(e.target.value as Language)}
            >
              <option value="zh">{t("settings.languageZh")}</option>
              <option value="en">{t("settings.languageEn")}</option>
            </select>
          </div>
        </section>

        {/* 2. Style Theme Panel */}
        <section className="settings-card">
          <h2 className="settings-card__title">{t("settings.appearance")}</h2>
          <div className="theme-toggle-row">
            <span>{t("settings.theme")}</span>
            <button type="button" className="theme-btn theme-btn--outline" onClick={handleToggleTheme}>
              {theme === "dark" ? t("settings.themeDark") : t("settings.themeLight")}
            </button>
          </div>
        </section>

        {/* 4. NAS Mount Configuration Panel */}
        <section className="settings-card">
          <h2 className="settings-card__title">{t("settings.nas")}</h2>
          
          <div className="nas-status-badge-row">
            <span>{t("settings.nasStatus")}:</span>
            <span className={`nas-badge ${nasConnected ? "nas-badge--connected" : "nas-badge--disconnected"}`}>
              {nasConnected ? t("settings.nasConnected") : t("settings.nasDisconnected")}
            </span>
          </div>

          <div className="form-row-group" style={{ marginTop: "16px" }}>
            <div className="form-group">
              <label>{t("settings.nasProtocol")}</label>
              <select
                className="theme-select"
                value={nasProtocol}
                onChange={(e) => setNasProtocol(e.target.value)}
              >
                <option value="smb">SMB / CIFS (Recommended)</option>
                <option value="nfs">NFS</option>
                <option value="afp">AFP (Apple Filing Protocol)</option>
              </select>
            </div>

            <div className="form-group" style={{ marginLeft: "20px" }}>
              <label>{t("settings.nasHost")}</label>
              <input
                type="text"
                className="theme-input"
                value={nasHost}
                onChange={(e) => setNasHost(e.target.value)}
                placeholder="192.168.1.100"
              />
            </div>
          </div>

          <div className="form-group" style={{ marginTop: "16px" }}>
            <label>{t("settings.nasShare")}</label>
            <input
              type="text"
              className="theme-input"
              value={nasShare}
              onChange={(e) => setNasShare(e.target.value)}
              placeholder="/FileSeekShare"
            />
          </div>

          <div className="form-row-group" style={{ marginTop: "16px" }}>
            <div className="form-group">
              <label>{t("settings.nasUser")}</label>
              <input
                type="text"
                className="theme-input"
                value={nasUser}
                onChange={(e) => setNasUser(e.target.value)}
                placeholder="nas_user"
              />
            </div>

            <div className="form-group" style={{ marginLeft: "20px" }}>
              <label>{t("settings.nasPassword")}</label>
              <input
                type="password"
                className="theme-input"
                value={nasPassword}
                onChange={(e) => setNasPassword(e.target.value)}
                placeholder="••••••••"
              />
            </div>
          </div>

          <div className="nas-actions-row" style={{ marginTop: "24px" }}>
            <button
              type="button"
              className="theme-btn theme-btn--outline"
              disabled={nasTesting}
              onClick={handleNasTest}
            >
              {nasTesting ? t("settings.nasTesting") : t("settings.nasTest")}
            </button>
          </div>

          {nasTestResult && (
            <div className={`nas-test-feedback-box ${nasTestResult === "success" ? "nas-test-feedback-box--success" : "nas-test-feedback-box--failed"}`}>
              {nasTestResult === "success" ? t("settings.nasSuccess") : t("settings.nasFailed", { reason: nasTestResult })}
            </div>
          )}
        </section>

        {/* 5. About Section */}
        <section className="settings-card">
          <h2 className="settings-card__title">{t("settings.about")}</h2>
          <p className="about-text">{t("settings.aboutText")}</p>
          <div className="version-info" style={{ marginTop: "16px", color: "var(--text-muted)" }}>
            {t("settings.version")}
          </div>
        </section>
      </div>
    </div>
  );
}
export default SettingsPanel;
