import { useState, type FormEvent } from "react";

import { Icon } from "../../../components/Icon";
import { useTranslate } from "../../../i18n/useTranslate";
import type { AgentConnectionResult, AgentSettings, AgentSettingsInput } from "../types";

interface AgentSettingsCardProps {
  settings: AgentSettings;
  onSave: (input: AgentSettingsInput) => Promise<boolean>;
  onTest: (input: AgentSettingsInput) => Promise<AgentConnectionResult>;
  loading?: boolean;
}

export function AgentSettingsCard({
  settings,
  onSave,
  onTest,
  loading = false,
}: AgentSettingsCardProps) {
  const t = useTranslate();
  const [baseUrl, setBaseUrl] = useState(settings.base_url);
  const [model, setModel] = useState(settings.model);
  const [apiKey, setApiKey] = useState("");
  const [saveError, setSaveError] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<AgentConnectionResult | null>(null);
  const [testing, setTesting] = useState(false);

  const currentInput = () => ({
    base_url: baseUrl.trim(),
    model: model.trim(),
    api_key: apiKey.trim() || null,
  });

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSaveError(null);
    try {
      await onSave(currentInput());
      setApiKey("");
    } catch (error) {
      setSaveError(
        error instanceof Error
          ? error.message
          : t("settings.agentSaveFailed", "保存检索智能体设置失败"),
      );
    }
  };

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      setTestResult(await onTest(currentInput()));
    } catch (error) {
      setTestResult({
        success: false,
        message:
          error instanceof Error
            ? error.message
            : t("settings.agentTestFailed", "测试 Agent 连接失败"),
      });
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className="settings-agent-manager" aria-label={t("settings.agentTitle", "检索智能体设置")}>
      <div className="settings-card-header">
        <div className="settings-card-heading">
          <span className="settings-card-icon">
            <Icon name="settings" size={19} />
          </span>
          <div>
            <h2>{t("settings.agentTitle", "检索智能体设置")}</h2>
            <p>{t("settings.agentDescription", "配置 OpenAI 兼容接口，用于检索增强搜索")}</p>
          </div>
        </div>
      </div>
      <form className="settings-drive-form settings-agent-form" onSubmit={handleSubmit}>
        <div className="settings-drive-fields">
          <label className="settings-field">
            <span>{t("settings.agentBaseUrl", "Agent 地址")}</span>
            <input
              value={baseUrl}
              onChange={(event) => setBaseUrl(event.target.value)}
              placeholder="https://api.example.com/v1"
              disabled={loading}
              required
            />
          </label>
          <label className="settings-field">
            <span>{t("settings.agentModel", "Agent 模型")}</span>
            <input
              value={model}
              onChange={(event) => setModel(event.target.value)}
              placeholder="retrieval-expert"
              disabled={loading}
              required
            />
          </label>
          <label className="settings-field">
            <span>{t("settings.agentApiKey", "API Key")}</span>
            <input
              type="password"
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
              placeholder={
                settings.api_key_configured
                  ? t("settings.agentApiKeyPreserved", "已配置，留空保留")
                  : "sk-..."
              }
              disabled={loading}
              autoComplete="new-password"
            />
          </label>
        </div>
        <p className="settings-agent-status">
          {settings.api_key_configured
            ? t("settings.agentReady", "检索增强搜索已就绪")
            : t("settings.agentIncomplete", "请配置 Agent 地址、模型和 API Key 后使用检索增强搜索")}
        </p>
        {loading && <p className="settings-empty">{t("settings.loading", "正在读取设置...")}</p>}
        {saveError && <p className="settings-inline-error" role="alert">{saveError}</p>}
        {testResult && (
          <p
            className={`settings-agent-test-result ${testResult.success ? "is-success" : "is-error"}`}
            role="status"
          >
            {testResult.message}
          </p>
        )}
        <div className="settings-agent-actions">
          <button className="settings-submit" type="submit" disabled={loading}>
            {t("settings.save", "保存")}
          </button>
          <button
            className="settings-submit settings-agent-test"
            type="button"
            onClick={handleTest}
            disabled={loading || testing}
          >
            {testing
              ? t("settings.agentTesting", "正在测试...")
              : t("settings.agentTest", "测试连接")}
          </button>
        </div>
      </form>
    </div>
  );
}
