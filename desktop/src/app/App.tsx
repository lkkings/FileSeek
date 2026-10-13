import { I18nProvider } from "@lingui/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { i18n } from "../i18n/i18n";
import { AppShell } from "./AppShell";
import { Router } from "./router";
import { SettingsPreferencesProvider } from "../features/settings";
import { ReadinessGate } from "../features/readiness";
import { LicenseProvider } from "../features/license";
import { UpdateBanner } from "../features/update";

const queryClient = new QueryClient();

export default function App() {
  return (
    <I18nProvider i18n={i18n}>
      <QueryClientProvider client={queryClient}>
        <SettingsPreferencesProvider>
          <LicenseProvider>
            <ReadinessGate>
              <UpdateBanner />
              <AppShell>
                <Router />
              </AppShell>
            </ReadinessGate>
          </LicenseProvider>
        </SettingsPreferencesProvider>
      </QueryClientProvider>
    </I18nProvider>
  );
}
