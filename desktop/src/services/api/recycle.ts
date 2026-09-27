import { defaultClient, type ApiClient, type ApiResponse } from "./client";

export interface RecycleItem {
  id: string;
  original_file_id: string;
  original_name: string;
  original_path: string;
  deleted_at: string;
  file_type: string;
  size: string;
}

export interface RecycleListResponse {
  items: RecycleItem[];
  page_number: number;
  page_size: number;
  total: number;
  has_more: boolean;
}

export function listRecycle(page: number = 1, pageSize: number = 20, client: ApiClient = defaultClient): Promise<ApiResponse<RecycleListResponse>> {
  const parameters = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });
  return client.get<RecycleListResponse>(`/recycle?${parameters.toString()}`);
}

export function deleteRecycleBatch(itemIds: string[], client: ApiClient = defaultClient): Promise<ApiResponse<void>> {
  return client.delete<void>("/recycle", { item_ids: itemIds });
}

export function restoreRecycleBatch(itemIds: string[], client: ApiClient = defaultClient): Promise<ApiResponse<void>> {
  return client.post<void>("/recycle/restore", { item_ids: itemIds });
}

export function addFilesToRecycle(fileIds: string[], client: ApiClient = defaultClient): Promise<ApiResponse<void>> {
  return client.post<void>("/recycle", { file_ids: fileIds });
}
