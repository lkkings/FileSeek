import { I18nProvider } from "@lingui/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { i18n } from "../i18n/i18n";
import { AppShell } from "./AppShell";
import { Router } from "./router";

const queryClient = new QueryClient();

export default function App() {
  return (
    <I18nProvider i18n={i18n}>
      <QueryClientProvider client={queryClient}>
        <AppShell>
          <Router />
        </AppShell>
      </QueryClientProvider>
    </I18nProvider>
  );
}
