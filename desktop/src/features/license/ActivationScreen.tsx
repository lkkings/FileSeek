import { type FormEvent, useState } from "react";

import { useTranslate } from "../../i18n/useTranslate";
import {
  activateLicense,
  isActivationError,
  openLibraryFolder,
  recheckLicense,
  type ActivationError,
} from "../../services/tauri/license";
import { openExternalUrl } from "../../services/tauri/opener";
import { useLicense } from "./LicenseContext";
import { activationErrorMessage, unlicensedMessage } from "./messages";
import "./license.css";

function asActivationError(error: unknown): ActivationError {
  return isActivationError(error) ? error : { kind: "server", code: String(error) };
}

/**
 * All there is without a valid license: enter a key, buy one, or — when the license is
 * only waiting to be checked online — try again. The library folder stays one click away,
 * so nobody thinks their files are locked up.
 */
export function ActivationScreen() {
  const t = useTranslate();
  const { entitlement, setEntitlement } = useLicense();
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ActivationError | null>(null);
  const [folderError, setFolderError] = useState(false);
  const offline = entitlement.reason === "offline_expired";
  const noDevice = entitlement.reason === "no_device";

  async function run(action: () => Promise<typeof entitlement>) {
    setBusy(true);
    setError(null);
    try {
      setEntitlement(await action());
    } catch (caught) {
      setError(asActivationError(caught));
    } finally {
      setBusy(false);
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    void run(() => activateLicense(key));
  }

  return (
    <main className="readiness-setup" aria-labelledby="activation-title">
      <div className="readiness-setup-card license-activation">
        <h1 id="activation-title">{t("license.screenTitle", "激活 FileSeek")}</h1>
        <p className={`readiness-setup-lead${entitlement.reason === "none" ? "" : " license-reason"}`} role="status">
          {unlicensedMessage(entitlement.reason, t)}
        </p>
        {entitlement.clockAnomaly && (
          <p className="readiness-setup-lead">{t("license.clockAnomaly", "系统时间异常，请检查电脑的日期和时间。")}</p>
        )}

        {offline && (
          <div className="license-dialog-actions">
            <button type="button" className="license-button is-primary" disabled={busy} onClick={() => void run(recheckLicense)}>
              {busy ? t("license.checking", "正在验证…") : t("license.retry", "重试")}
            </button>
          </div>
        )}

        {!noDevice && (
          <form className="license-field" onSubmit={submit}>
            <label htmlFor="license-key">{t("license.keyLabel", "许可证密钥")}</label>
            <input
              id="license-key"
              value={key}
              autoComplete="off"
              spellCheck={false}
              placeholder="KG-XXXXXXXX-XXXXXXXX-XXXXXXXX-XXXXXXXX"
              aria-invalid={error !== null}
              aria-describedby={error ? "license-key-error" : undefined}
              onChange={(event) => setKey(event.target.value)}
            />
            {error && (
              <p id="license-key-error" className="license-error" role="alert">
                {activationErrorMessage(error, t)}
              </p>
            )}
            <div className="license-dialog-actions">
              {entitlement.purchaseUrl && (
                <button type="button" className="license-link" onClick={() => void openExternalUrl(entitlement.purchaseUrl)}>
                  {t("license.buy", "购买许可证")}
                </button>
              )}
              <button type="submit" className="license-button is-primary" disabled={busy || key.trim() === ""}>
                {busy && !offline ? t("license.activating", "正在激活…") : t("license.activate", "激活")}
              </button>
            </div>
          </form>
        )}

        <div className="license-library">
          <p>{t("license.libraryHint", "已导入的原文件仍在文件库目录中，可以直接打开。")}</p>
          <button
            type="button"
            className="license-button"
            onClick={() => {
              setFolderError(false);
              openLibraryFolder().catch(() => setFolderError(true));
            }}
          >
            {t("license.openLibrary", "打开文件库目录")}
          </button>
          {folderError && (
            <p className="license-error" role="alert">
              {t("license.openLibraryFailed", "文件库目录不存在或无法打开。")}
            </p>
          )}
        </div>
      </div>
    </main>
  );
}
