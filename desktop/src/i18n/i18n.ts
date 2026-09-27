import { i18n } from "@lingui/core";

export const defaultLocale = "zh-CN";

i18n.load(defaultLocale, {});
i18n.activate(defaultLocale);

export { i18n };
