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
  return client.post<ApiFolder>("/library/folders", input);
}

export function updateFolder(folderId: string, input: FolderInput, client: ApiClient = defaultClient): Promise<ApiResponse<ApiFolder>> {
  return client.put<ApiFolder>(`/library/folders/${encodeURIComponent(folderId)}`, input);
}

export function deleteFolder(folderId: string, client: ApiClient = defaultClient): Promise<ApiResponse<null>> {
  return client.delete<null>(`/library/folders/${encodeURIComponent(folderId)}`);
}
