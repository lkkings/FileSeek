import { type ReactNode, useState } from "react";

import { useTranslate } from "../../i18n/useTranslate";
import { ActivationScreen } from "../license";
import { loadSetupPromptShown } from "../../services/preferences";
import { ReadinessProblem } from "./ReadinessProblem";
import { SetupScreen } from "./SetupScreen";
import { SuggestedSettingsDialog } from "./SuggestedSettingsDialog";
import { useReadiness } from "./useReadiness";
import "./readiness.css";

/**
 * Holds the app back until there is a license and the backend is ready, then keeps out of
 * the way: a restart or failure later on shows a banner over the app instead of taking it
 * away. Losing the license does take it away: without one there is only activation.
 */
export function ReadinessGate({ children }: { children: ReactNode }) {
  const t = useTranslate();
  const { readiness, everReady, installing } = useReadiness();
  const [promptPending, setPromptPending] = useState(() => !loadSetupPromptShown());

  const state = readiness?.state;
  if (state === "activation") {
    return <ActivationScreen />;
  }
  if (!everReady || state === "license_check") {
    return <SetupScreen readiness={readiness} installing={installing} />;
  }

  const problem = state === "failed" || state === "repair_needed";
  const reconnecting = !problem && state !== "ready";

  return (
    <>
      {(problem || reconnecting) && readiness && (
        <div className={`readiness-banner${problem ? " is-problem" : ""}`}>
          {problem ? (
            <ReadinessProblem readiness={readiness} />
          ) : (
            <p role="status">{t("readiness.reconnecting", "后端服务正在重新启动…")}</p>
          )}
        </div>
      )}
      {children}
      {promptPending && state === "ready" && <SuggestedSettingsDialog onClose={() => setPromptPending(false)} />}
    </>
  );
}
