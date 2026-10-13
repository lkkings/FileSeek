import { useState } from "react";

import { useTranslate } from "../../i18n/useTranslate";
import { deactivateLicense, isActivationError, type ActivationError } from "../../services/tauri/license";
import { openExternalUrl } from "../../services/tauri/opener";
import { useLicense } from "./LicenseContext";
import { activationErrorMessage, licenseFacts } from "./messages";
import "./license.css";

/** Settings → License: what this device has, unbind it, buy or renew. */
export function LicenseCard() {
  const t = useTranslate();
  const { entitlement, setEntitlement } = useLicense();
  const [busy, setBusy] = useState(false);
  const [confirmUnbind, setConfirmUnbind] = useState(false);
  const [error, setError] = useState<ActivationError | null>(null);
  // Development builds and the browser preview have no license to unbind.
  const activated = entitlement.licenseId !== null;

  async function unbind() {
    setBusy(true);
    setError(null);
    try {
      // Unlicensed now: Rust stops the backend and the activation screen takes over.
      setEntitlement(await deactivateLicense());
    } catch (caught) {
      setError(isActivationError(caught) ? caught : { kind: "server", code: String(caught) });
    } finally {
      setBusy(false);
      setConfirmUnbind(false);
    }
  }

  return (
    <section className="settings-card license-card" aria-labelledby="license-card-title">
      <div className="settings-card-header">
        <div className="settings-card-heading">
          <div>
            <h2 id="license-card-title">{t("license.cardTitle", "许可")}</h2>
            {licenseFacts(entitlement, t).map((fact) => (
              <p key={fact} className="license-summary">
                {fact}
              </p>
            ))}
          </div>
        </div>
      </div>

      <div className="license-card-actions">
        {entitlement.purchaseUrl && (
          <button type="button" className="license-button" onClick={() => void openExternalUrl(entitlement.purchaseUrl)}>
            {t("license.buyOrRenew", "购买/续费")}
          </button>
        )}
        {activated && !confirmUnbind && (
          <button type="button" className="license-button" disabled={busy} onClick={() => setConfirmUnbind(true)}>
            {t("license.unbind", "解绑本机")}
          </button>
        )}
        {confirmUnbind && (
          <>
            <span>{t("license.unbindConfirm", "解绑后本机需要重新激活才能使用，许可证可以在其他设备上激活。确定吗？")}</span>
            <button type="button" className="license-button is-primary" disabled={busy} onClick={() => void unbind()}>
              {t("license.unbindYes", "确定解绑")}
            </button>
            <button type="button" className="license-button" onClick={() => setConfirmUnbind(false)}>
              {t("common.cancel", "取消")}
            </button>
          </>
        )}
      </div>

      {error && (
        <p className="license-error" role="alert">
          {error.kind === "network"
            ? t("license.errorNetworkKeep", "无法连接许可服务器，请稍后重试，或在客户门户中解绑。")
            : activationErrorMessage(error, t)}
        </p>
      )}
    </section>
  );
}
