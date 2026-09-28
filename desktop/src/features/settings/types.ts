import type {
  ClassifierLabels,
  StorageConnectionResult,
  StorageLocation,
  StorageLocationInput,
  StorageProtocol,
} from "../../services/api/settings";

export type LocalePreference = "zh-CN" | "en-US";
export type TagCategory = "documentTags" | "imageTags" | "videoTags";

export interface SettingsPreferences {
  locale: LocalePreference;
  documentTags: string[];
  imageTags: string[];
  videoTags: string[];
  storageDrives: StorageLocation[];
}

export type { ClassifierLabels, StorageConnectionResult, StorageLocation, StorageLocationInput, StorageProtocol };
