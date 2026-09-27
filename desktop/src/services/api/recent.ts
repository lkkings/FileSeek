import { defaultClient, type ApiClient, type ApiResponse } from "./client";

export interface RecentFile {
  id: string;
  name: string;
  file_type: string;
  category: string;
  size: string;
  modified: string;
  folder_id: string | null;
  path: string;
}

export interface RecentAccessItem {
  id: number;
  file_id: string;
  accessed_at: string;
  file: RecentFile | null;
}

export interface RecentListResponse {
  items: RecentAccessItem[];
  page_number: number;
  page_size: number;
  total: number;
  has_more: boolean;
}

export function listRecent(page: number = 1, pageSize: number = 20, client: ApiClient = defaultClient): Promise<ApiResponse<RecentListResponse>> {
  const parameters = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });
  return client.get<RecentListResponse>(`/recent?${parameters.toString()}`);
}

export function addRecent(fileId: string, client: ApiClient = defaultClient): Promise<ApiResponse<void>> {
  return client.post<void>("/recent", { file_id: fileId });
}

export function deleteRecentRecord(recordId: number, client: ApiClient = defaultClient): Promise<ApiResponse<void>> {
  return client.delete<void>(`/recent/${recordId}`);
}
