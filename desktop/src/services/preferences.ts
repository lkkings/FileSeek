import type { LocalePreference } from "../features/settings/types";

const LOCALE_STORAGE_KEY = "fileseek.locale.v1";

export const defaultLocale: LocalePreference = "zh-CN";

export function loadLocale(): LocalePreference {
  try {
    const value = window.localStorage.getItem(LOCALE_STORAGE_KEY);
    if (value === "zh-CN" || value === "en-US") return value;
  } catch {
    return defaultLocale;
  }
  return defaultLocale;
}

export function saveLocale(locale: LocalePreference) {
  try {
    window.localStorage.setItem(LOCALE_STORAGE_KEY, locale);
  } catch {
    return;
  }
}
