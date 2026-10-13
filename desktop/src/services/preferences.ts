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

const SETUP_PROMPT_STORAGE_KEY = "fileseek.setupPromptShown.v1";

/** Whether the post-install "suggested settings" dialog has been shown (and dismissed). */
export function loadSetupPromptShown(): boolean {
  try {
    return window.localStorage.getItem(SETUP_PROMPT_STORAGE_KEY) === "1";
  } catch {
    // Storage unavailable: treat as shown, so the dialog does not come back every launch.
    return true;
  }
}

export function markSetupPromptShown() {
  try {
    window.localStorage.setItem(SETUP_PROMPT_STORAGE_KEY, "1");
  } catch {
    return;
  }
}

export function saveLocale(locale: LocalePreference) {
  try {
    window.localStorage.setItem(LOCALE_STORAGE_KEY, locale);
  } catch {
    return;
  }
}
