import { defaultClient, type ApiClient, type ApiResponse } from "./client";

export interface FileItem {
  file_id: string;
  file_name: string;
  file_type: string;
  category: string;
  path: string;
  size: number | null;
  modified: string | null;
  tags: string[];
  score: number;
  metadata?: FileMetadata | null;
  chunks?: unknown[] | null;
}

export interface FileMetadata {
  scene?: string;
  duration?: string;
  description?: string;
  text?: string;
  start_time?: number;
  end_time?: number;
  page_number?: number;
  line_number?: number;
  chunk_index?: number;
  [key: string]: unknown;
}

export interface SearchRequest {
  query: string;
  folder_id?: string | null;
  categories?: string[];
  tag?: string | null;
  name_query?: string | null;
  min_size_m?: number | null;
  max_size_m?: number | null;
  start_date?: string | null;
  end_date?: string | null;
  sort_by: "relevance" | "created_at" | "size";
  sort_order: "asc" | "desc";
  page_number?: number;
  page_size?: number;
}

export interface EnhancedSearchRequest {
  query: string;
  folder_id?: string | null;
  sort_by: "relevance" | "created_at" | "size";
  sort_order: "asc" | "desc";
  page_number?: number;
  page_size?: number;
}

export interface SearchResponseData {
  items: FileItem[];
  total: number;
  page_number: number;
  page_size: number;
  has_more: boolean;
  counter: Record<string, number>
}

export type EnhancedSearchProgressEventType =
  | "status"
  | "reasoning"
  | "tool_call"
  | "tool_result"
  | "result"
  | "error";

export interface EnhancedSearchProgressEvent {
  type: EnhancedSearchProgressEventType;
  phase?: string | null;
  message?: string | null;
  round_number?: number | null;
  content?: string | null;
  tool_name?: string | null;
  query?: string | null;
  categories?: string[] | null;
  name_query?: string | null;
  candidate_count?: number | null;
  total?: number | null;
  result?: SearchResponseData | null;
  error?: string | null;
}

export function searchFiles(request: SearchRequest, client: ApiClient = defaultClient): Promise<ApiResponse<SearchResponseData>> {
  return client.post<SearchResponseData>("/search", request);
}

export function enhancedSearchFiles(
  request: EnhancedSearchRequest,
  client: ApiClient = defaultClient,
): Promise<ApiResponse<SearchResponseData>> {
  return client.post<SearchResponseData>("/search/enhanced", request);
}

export interface WarmupResponseData {
  started: boolean;
}

/**
 * 预热查询模型：查询模型进程空闲退出后，第一次搜索要等几秒冷启动。
 * 搜索框获得焦点时调用它，后端在后台把模型加载起来，用户提交搜索时多半已经就绪。
 */
export function warmupSearch(client: ApiClient = defaultClient): Promise<ApiResponse<WarmupResponseData>> {
  return client.post<WarmupResponseData>("/search/warmup");
}
