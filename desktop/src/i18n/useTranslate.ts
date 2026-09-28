import { useLingui } from "@lingui/react";

export function useTranslate() {
  const { i18n } = useLingui();

  return (id: string, message: string, values?: Record<string, unknown>) =>
    i18n._(id, values ?? {}, { message });
}
