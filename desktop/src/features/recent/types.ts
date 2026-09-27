import type { FileItem } from "../../services/api/search";

export interface RecentRecord {
  recordId: number;
  fileId: string;
  accessedAt: string;
  file: FileItem;
}

export interface RecentPageData {
  items: RecentRecord[];
  pageNumber: number;
  pageSize: number;
  total: number;
  hasMore: boolean;
}

export interface RecentDeleteResult {
  successCount: number;
  failureCount: number;
  failedRecordIds: number[];
  errors: string[];
}
