import { createContext } from "react";

import type {
  AgentSettings,
  AgentConnectionResult,
  AgentSettingsInput,
  StorageConnectionResult,
  StorageLocationInput,
  LocalePreference,
  SettingsPreferences,
} from "../types";

export interface SettingsPreferencesContextValue {
  preferences: SettingsPreferences;
  agentSettings: AgentSettings;
  loading: boolean;
  loadError: string | null;
  setLocale: (locale: LocalePreference) => void;
  addTag: (category: "documentTags" | "imageTags" | "videoTags", tag: string) => Promise<boolean>;
  removeTag: (category: "documentTags" | "imageTags" | "videoTags", tag: string) => Promise<void>;
  addStorageDrive: (drive: StorageLocationInput) => Promise<boolean>;
  removeStorageDrive: (driveId: string) => Promise<void>;
  testStorageDrive: (driveId: string) => Promise<StorageConnectionResult>;
  saveAgentSettings: (input: AgentSettingsInput) => Promise<boolean>;
  testAgentSettings: (input: AgentSettingsInput) => Promise<AgentConnectionResult>;
}

export const SettingsPreferencesContext = createContext<SettingsPreferencesContextValue | null>(null);
