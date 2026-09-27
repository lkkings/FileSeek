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

export function listFolders(client: ApiClient = defaultClient): Promise<ApiResponse<ApiFolder[]>> {
  return client.get<ApiFolder[]>("/library/folders");
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
