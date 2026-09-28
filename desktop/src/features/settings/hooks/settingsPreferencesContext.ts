import { createContext } from "react";

import type {
  StorageConnectionResult,
  StorageLocationInput,
  LocalePreference,
  SettingsPreferences,
} from "../types";

export interface SettingsPreferencesContextValue {
  preferences: SettingsPreferences;
  loading: boolean;
  loadError: string | null;
  setLocale: (locale: LocalePreference) => void;
  addTag: (category: "documentTags" | "imageTags" | "videoTags", tag: string) => Promise<boolean>;
  removeTag: (category: "documentTags" | "imageTags" | "videoTags", tag: string) => Promise<void>;
  addStorageDrive: (drive: StorageLocationInput) => Promise<boolean>;
  removeStorageDrive: (driveId: string) => Promise<void>;
  testStorageDrive: (driveId: string) => Promise<StorageConnectionResult>;
}

export const SettingsPreferencesContext = createContext<SettingsPreferencesContextValue | null>(null);
