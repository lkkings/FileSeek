import { useLingui } from "@lingui/react";

export function useTranslate() {
  const { i18n } = useLingui();

  return (id: string, message: string) => i18n._({ id, message });
}
