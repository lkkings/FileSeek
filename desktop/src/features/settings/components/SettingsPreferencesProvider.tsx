import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { activateLocale } from "../../../i18n/i18n";
import { errorText, type ApiClient } from "../../../services/api/client";
import {
  getAgentSettings,
  createStorageLocation,
  deleteStorageLocation,
  listClassifierLabels,
  listStorageLocations,
  replaceClassifierLabels,
  testAgentSettings as testAgentSettingsApi,
  testStorageLocation,
  updateAgentSettings,
} from "../../../services/api/settings";
import { loadLocale, saveLocale } from "../../../services/preferences";
import { useTranslate } from "../../../i18n/useTranslate";
import type {
  AgentSettings,
  AgentConnectionResult,
  AgentSettingsInput,
  ClassifierLabels,
  LocalePreference,
  SettingsPreferences,
  StorageLocationInput,
} from "../types";
import type { SettingsPreferencesContextValue } from "../hooks/settingsPreferencesContext";
import { SettingsPreferencesContext } from "../hooks/settingsPreferencesContext";

const classifierLabelsQueryKey = ["settings", "classifier-labels"] as const;
const storageLocationsQueryKey = ["settings", "storage-locations"] as const;
const agentSettingsQueryKey = ["settings", "agent"] as const;
const labelKeys = {
  documentTags: "document_labels",
  imageTags: "image_labels",
  videoTags: "video_labels",
} as const;
type LabelKey = (typeof labelKeys)[keyof typeof labelKeys];

const emptyLabels: ClassifierLabels = {
  document_labels: [],
  image_labels: [],
  video_labels: [],
  version: "",
};
const emptyAgentSettings: AgentSettings = {
  base_url: "",
  model: "",
  api_key_configured: false,
};

export function SettingsPreferencesProvider({
  children,
  client,
}: {
  children: ReactNode;
  client?: ApiClient;
}) {
  const t = useTranslate();
  const queryClient = useQueryClient();
  const [locale, setLocale] = useState<LocalePreference>(() => loadLocale());

  useEffect(() => {
    saveLocale(locale);
    activateLocale(locale);
  }, [locale]);

  const labelsQuery = useQuery({
    queryKey: classifierLabelsQueryKey,
    queryFn: async () => {
      const response = await listClassifierLabels(client);
      if (response.status !== "success" || !response.data) {
        throw new Error(errorText(response.error) || t("settings.loadFailed", "无法读取设置"));
      }
      return response.data;
    },
  });

  const locationsQuery = useQuery({
    queryKey: storageLocationsQueryKey,
    queryFn: async () => {
      const response = await listStorageLocations(client);
      if (response.status !== "success" || !response.data) {
        throw new Error(errorText(response.error) || t("settings.loadFailed", "无法读取设置"));
      }
      return response.data;
    },
  });

  const agentSettingsQuery = useQuery({
    queryKey: agentSettingsQueryKey,
    queryFn: async () => {
      const response = await getAgentSettings(client);
      if (response.status !== "success" || !response.data) {
        throw new Error(errorText(response.error) || t("settings.loadFailed", "无法读取设置"));
      }
      return response.data;
    },
  });

  const replaceLabelsMutation = useMutation({
    mutationFn: async (labels: ClassifierLabels) => {
      const response = await replaceClassifierLabels(labels, client);
      if (response.status !== "success" || !response.data) {
        throw new Error(errorText(response.error) || t("settings.saveFailed", "保存设置失败"));
      }
      return response.data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: classifierLabelsQueryKey }),
  });

  const createLocationMutation = useMutation({
    mutationFn: async (input: StorageLocationInput) => {
      const response = await createStorageLocation(input, client);
      if (response.status !== "success" || !response.data) {
        throw new Error(errorText(response.error) || t("settings.storageCreateFailed", "添加存储失败"));
      }
      return response.data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: storageLocationsQueryKey }),
  });

  const deleteLocationMutation = useMutation({
    mutationFn: async (locationId: string) => {
      const response = await deleteStorageLocation(locationId, client);
      if (response.status !== "success" || !response.data) {
        throw new Error(errorText(response.error) || t("settings.storageDeleteFailed", "移除存储失败"));
      }
      return response.data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: storageLocationsQueryKey }),
  });

  const testLocationMutation = useMutation({
    mutationFn: async (locationId: string) => {
      const response = await testStorageLocation(locationId, client);
      if (response.status !== "success" || !response.data) {
        throw new Error(errorText(response.error) || t("settings.connectionTestFailed", "测试连接失败"));
      }
      return response.data;
    },
  });

  const updateAgentSettingsMutation = useMutation({
    mutationFn: async (input: AgentSettingsInput) => {
      const response = await updateAgentSettings(input, client);
      if (response.status !== "success" || !response.data) {
        throw new Error(
          errorText(response.error) || t("settings.agentSaveFailed", "保存检索智能体设置失败"),
        );
      }
      return response.data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: agentSettingsQueryKey }),
  });

  const testAgentSettingsMutation = useMutation({
    mutationFn: async (input: AgentSettingsInput): Promise<AgentConnectionResult> => {
      const response = await testAgentSettingsApi(input, client);
      if (response.status !== "success" || !response.data) {
        throw new Error(
          errorText(response.error) || t("settings.agentTestFailed", "测试 Agent 连接失败"),
        );
      }
      return response.data;
    },
  });

  const labels = labelsQuery.data ?? emptyLabels;
  const locations = locationsQuery.data ?? [];
  const agentSettings = agentSettingsQuery.data ?? emptyAgentSettings;

  const preferences: SettingsPreferences = useMemo(() => ({
    locale,
    documentTags: labels.document_labels,
    imageTags: labels.image_labels,
    videoTags: labels.video_labels,
    storageDrives: locations,
  }), [locale, labels, locations]);

  const addTag = async (category: "documentTags" | "imageTags" | "videoTags", tag: string) => {
    const normalized = tag.trim();
    const labelKey = labelKeys[category] as LabelKey;
    if (!normalized || labels[labelKey].includes(normalized)) {
      return false;
    }

    await replaceLabelsMutation.mutateAsync({
      ...labels,
      [labelKey]: [...labels[labelKey], normalized],
    } as ClassifierLabels);
    return true;
  };

  const removeTag = async (category: "documentTags" | "imageTags" | "videoTags", tag: string) => {
    const labelKey = labelKeys[category] as LabelKey;
    await replaceLabelsMutation.mutateAsync({
      ...labels,
      [labelKey]: labels[labelKey].filter((item) => item !== tag),
    } as ClassifierLabels);
  };

  const addStorageDrive = async (drive: StorageLocationInput) => {
    await createLocationMutation.mutateAsync(drive);
    return true;
  };

  const removeStorageDrive = async (driveId: string) => {
    await deleteLocationMutation.mutateAsync(driveId);
  };

  const testStorageDrive = async (driveId: string) => testLocationMutation.mutateAsync(driveId);

  const saveAgentSettings = async (input: AgentSettingsInput) => {
    await updateAgentSettingsMutation.mutateAsync(input);
    return true;
  };

  const testAgentSettings = async (input: AgentSettingsInput) =>
    testAgentSettingsMutation.mutateAsync(input);

  const value = useMemo<SettingsPreferencesContextValue>(() => ({
    preferences,
    agentSettings,
    loading:
      labelsQuery.isPending || locationsQuery.isPending || agentSettingsQuery.isPending,
    loadError: labelsQuery.error instanceof Error
      ? labelsQuery.error.message
      : locationsQuery.error instanceof Error
        ? locationsQuery.error.message
        : agentSettingsQuery.error instanceof Error
          ? agentSettingsQuery.error.message
          : null,
    setLocale,
    addTag,
    removeTag,
    addStorageDrive,
    removeStorageDrive,
    testStorageDrive,
    saveAgentSettings,
    testAgentSettings,
  }), [
    preferences,
    agentSettings,
    labelsQuery.isPending,
    locationsQuery.isPending,
    agentSettingsQuery.isPending,
    labelsQuery.error,
    locationsQuery.error,
    agentSettingsQuery.error,
    labels,
    replaceLabelsMutation,
    createLocationMutation,
    deleteLocationMutation,
    testLocationMutation,
    updateAgentSettingsMutation,
    testAgentSettingsMutation,
  ]);

  return <SettingsPreferencesContext.Provider value={value}>{children}</SettingsPreferencesContext.Provider>;
}
