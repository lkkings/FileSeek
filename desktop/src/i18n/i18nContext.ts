import { createContext } from "react";
import type { TranslationKeys } from "./loc/zh";

export type Language = "zh" | "en";

export interface I18nContextType {
  language: Language;
  setLanguage: (lang: Language) => void;
  t: (key: TranslationKeys, variables?: Record<string, string | number>) => string;
}

export const I18nContext = createContext<I18nContextType | undefined>(undefined);
