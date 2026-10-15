import { defaultClient, type ApiClient, type ApiResponse } from "./client";

export interface ApiFolder {
  id: string;
  name: string;
  iconType: string;
  description: string;
  modified: string;
  file_count: number;
}

export interface FolderInput {
  name: string;
  iconType: string;
  description: string;
}

export interface MoveFilesToFolderInput {
  fileIds: string[];
  targetFolderId: string;
}

export interface BatchImportItem {
  path: string;
  storageId?: string;
}

export interface BatchImportInput {
  folderId: string;
  items: BatchImportItem[];
}

export interface ApiFolderSourceBinding {
  id: string;
  folder_id: string;
  storage_id: string;
  source_path: string;
  recursive: boolean;
  enabled: boolean;
  watch_status: string;
  last_error: string | null;
  last_error_at: string | null;
}

export interface FolderSourceBindingInput {
  storageId: string;
  path: string;
  recursive: boolean;
  enabled: boolean;
}

export interface BatchImportResponse {
  import_id: string;
  total: number;
}

export interface MoveFilesToFolderResponse {
  moved_count: number;
}

export function listFolders(client: ApiClient = defaultClient): Promise<ApiResponse<ApiFolder[]>> {
  return client.get<ApiFolder[]>("/library/folders");
}

export function listTags(client: ApiClient = defaultClient): Promise<ApiResponse<string[]>> {
  return client.get<string[]>("/library/tags");
 }

export function moveFilesToFolder(
  input: MoveFilesToFolderInput,
  client: ApiClient = defaultClient,
): Promise<ApiResponse<MoveFilesToFolderResponse>> {
  return client.post<MoveFilesToFolderResponse>("/library/files/move", {
    file_ids: input.fileIds,
    target_folder_id: input.targetFolderId,
  });
 }

export function createFolder(input: FolderInput, client: ApiClient = defaultClient): Promise<ApiResponse<ApiFolder>> {
  return client.post<ApiFolder>("/library/folders", {
    name: input.name,
    icon_type: input.iconType,
    description: input.description,
  });
}

export function startBatchImport(
  input: BatchImportInput,
  client: ApiClient = defaultClient,
): Promise<ApiResponse<BatchImportResponse>> {
  return client.post<BatchImportResponse>("/library/files/import", {
    folder_id: input.folderId,
    items: input.items.map((item) => ({
      path: item.path,
      storage_id: item.storageId ?? "local",
    })),
  });
}

export function listFolderSourceBindings(
  folderId: string,
  client: ApiClient = defaultClient,
): Promise<ApiResponse<ApiFolderSourceBinding[]>> {
  return client.get<ApiFolderSourceBinding[]>(
    `/library/folders/${encodeURIComponent(folderId)}/source-bindings`,
  );
}

export function createFolderSourceBinding(
  folderId: string,
  input: FolderSourceBindingInput,
  client: ApiClient = defaultClient,
): Promise<ApiResponse<ApiFolderSourceBinding>> {
  return client.post<ApiFolderSourceBinding>(
    `/library/folders/${encodeURIComponent(folderId)}/source-bindings`,
    toBindingPayload(input),
  );
}

export function updateFolderSourceBinding(
  folderId: string,
  bindingId: string,
  input: FolderSourceBindingInput,
  client: ApiClient = defaultClient,
): Promise<ApiResponse<ApiFolderSourceBinding>> {
  return client.patch<ApiFolderSourceBinding>(
    `/library/folders/${encodeURIComponent(folderId)}/source-bindings/${encodeURIComponent(bindingId)}`,
    toBindingPayload(input),
  );
}

export function deleteFolderSourceBinding(
  folderId: string,
  bindingId: string,
  client: ApiClient = defaultClient,
): Promise<ApiResponse<null>> {
  return client.delete<null>(
    `/library/folders/${encodeURIComponent(folderId)}/source-bindings/${encodeURIComponent(bindingId)}`,
  );
}

function toBindingPayload(input: FolderSourceBindingInput) {
  return {
    storage_id: input.storageId,
    path: input.path,
    recursive: input.recursive,
    enabled: input.enabled,
  };
}

export function updateFolder(folderId: string, input: FolderInput, client: ApiClient = defaultClient): Promise<ApiResponse<ApiFolder>> {
  return client.put<ApiFolder>(`/library/folders/${encodeURIComponent(folderId)}`, {
    name: input.name,
    icon_type: input.iconType,
    description: input.description,
  });
}

export function deleteFolder(folderId: string, client: ApiClient = defaultClient): Promise<ApiResponse<null>> {
  return client.delete<null>(`/library/folders/${encodeURIComponent(folderId)}`);
}
