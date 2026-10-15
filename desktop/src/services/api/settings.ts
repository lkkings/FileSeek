import { defaultClient, type ApiClient, type ApiResponse } from "./client";

export interface ClassifierLabels {
  document_labels: string[];
  image_labels: string[];
  video_labels: string[];
  version: string;
}

export interface AgentSettings {
  base_url: string;
  model: string;
  api_key_configured: boolean;
}

export interface AgentSettingsInput {
  base_url: string;
  model: string;
  api_key?: string | null;
}

export interface AgentConnectionResult {
  success: boolean;
  message: string;
}

export type StorageLocationType = "local" | "nas" | "external";
export type StorageProtocol = "file" | "mounted" | "smb" | "nfs" | "webdav";
export type StorageStatus = "active" | "deleted";

export interface StorageLocation {
  id: string;
  type: StorageLocationType;
  name: string;
  protocol: StorageProtocol;
  endpoint: string;
  root_path: string;
  account: string | null;
  status: StorageStatus;
  is_system: boolean;
}

export interface StorageLocationInput {
  id?: string;
  name: string;
  protocol: StorageProtocol;
  endpoint: string;
  root_path?: string;
  account?: string | null;
  password?: string | null;
}

export interface StorageLocationDeletion {
  id: string;
  status: StorageStatus;
  affected_files: number;
}

export interface StorageConnectionResult {
  success: boolean;
  message: string;
}

export interface StorageDirectoryEntry {
  name: string;
  kind: "directory" | "file";
  source_path: string;
  size: number;
  modified: string;
}

export interface StorageDirectoryResponse {
  current_path: string;
  entries: StorageDirectoryEntry[];
}

export function listClassifierLabels(
  client: ApiClient = defaultClient,
): Promise<ApiResponse<ClassifierLabels>> {
  return client.get<ClassifierLabels>("/settings/classifier-labels");
}

export function getAgentSettings(
  client: ApiClient = defaultClient,
): Promise<ApiResponse<AgentSettings>> {
  return client.get<AgentSettings>("/settings/agent");
}

export function updateAgentSettings(
  input: AgentSettingsInput,
  client: ApiClient = defaultClient,
): Promise<ApiResponse<AgentSettings>> {
  return client.put<AgentSettings>("/settings/agent", {
    base_url: input.base_url,
    model: input.model,
    api_key: input.api_key ?? null,
  });
}

export function testAgentSettings(
  input: AgentSettingsInput,
  client: ApiClient = defaultClient,
): Promise<ApiResponse<AgentConnectionResult>> {
  return client.post<AgentConnectionResult>("/settings/agent/test", {
    base_url: input.base_url,
    model: input.model,
    api_key: input.api_key ?? null,
  });
}

export function replaceClassifierLabels(
  labels: ClassifierLabels,
  client: ApiClient = defaultClient,
): Promise<ApiResponse<ClassifierLabels>> {
  return client.put<ClassifierLabels>("/settings/classifier-labels", {
    document_labels: labels.document_labels,
    image_labels: labels.image_labels,
    video_labels: labels.video_labels,
  });
}

export function listStorageLocations(
  client: ApiClient = defaultClient,
): Promise<ApiResponse<StorageLocation[]>> {
  return client.get<StorageLocation[]>("/settings/storage-locations");
}

export function listStorageDirectory(
  locationId: string,
  path = "",
  client: ApiClient = defaultClient,
): Promise<ApiResponse<StorageDirectoryResponse>> {
  const parameters = new URLSearchParams({ path });
  return client.get<StorageDirectoryResponse>(
    `/settings/storage-locations/${encodeURIComponent(locationId)}/directory?${parameters.toString()}`,
  );
}

export function createStorageLocation(
  input: StorageLocationInput,
  client: ApiClient = defaultClient,
): Promise<ApiResponse<StorageLocation>> {
  return client.post<StorageLocation>("/settings/storage-locations", input);
}

export function updateStorageLocation(
  locationId: string,
  input: StorageLocationInput,
  client: ApiClient = defaultClient,
): Promise<ApiResponse<StorageLocation>> {
  return client.put<StorageLocation>(
    `/settings/storage-locations/${encodeURIComponent(locationId)}`,
    input,
  );
}

export function deleteStorageLocation(
  locationId: string,
  client: ApiClient = defaultClient,
): Promise<ApiResponse<StorageLocationDeletion>> {
  return client.delete<StorageLocationDeletion>(
    `/settings/storage-locations/${encodeURIComponent(locationId)}`,
  );
}

export function testStorageLocation(
  locationId: string,
  client: ApiClient = defaultClient,
): Promise<ApiResponse<StorageConnectionResult>> {
  return client.post<StorageConnectionResult>(
    `/settings/storage-locations/${encodeURIComponent(locationId)}/test`,
  );
}
