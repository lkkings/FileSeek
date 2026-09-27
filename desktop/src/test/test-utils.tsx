import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { I18nProvider } from "@lingui/react";
import { render, renderHook, type RenderHookResult, type RenderResult } from "@testing-library/react";
import type { ReactNode } from "react";

import { i18n } from "../i18n/i18n";

export function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
}

export function createTestWrapper() {
  const queryClient = createTestQueryClient();
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <I18nProvider i18n={i18n}>
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    </I18nProvider>
  );
  return { Wrapper, queryClient };
}

export function renderHookWithProviders<Props, Result>(
  callback: (props: Props) => Result,
): RenderHookResult<Result, Props> {
  const { Wrapper } = createTestWrapper();
  return renderHook(callback, { wrapper: Wrapper });
}

export function renderWithI18n(ui: ReactNode): RenderResult {
  return render(<I18nProvider i18n={i18n}>{ui}</I18nProvider>);
}

export function renderWithProviders(ui: ReactNode): RenderResult {
  const { Wrapper, queryClient } = createTestWrapper();
  void queryClient;
  return render(ui, { wrapper: Wrapper });
}
