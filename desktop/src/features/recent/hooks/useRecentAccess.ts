import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { useTranslate } from "../../../i18n/useTranslate";
import { defaultClient, errorText, type ApiClient } from "../../../services/api/client";
import { deleteRecentRecord, listRecent } from "../../../services/api/recent";
import type { FileItem } from "../../../services/api/search";
import type { RecentDeleteResult, RecentPageData } from "../types";

const RECENT_LIST_QUERY_KEY = ["recent", "list"] as const;

function toRecentFile(fileId: string, accessedAt: string, file: {
  id: string;
  name: string;
  file_type: string;
  category: string;
  size: string;
  modified: string;
  path: string;
} | null): FileItem {
  if (!file) {
    return {
      file_id: fileId,
      file_name: fileId,
      file_type: "",
      category: "document",
      path: "",
      size: null,
      modified: accessedAt,
      tags: [],
      score: 0,
      metadata: null,
      chunks: null,
    };
  }

  const size = Number(file.size);
  return {
    file_id: file.id,
    file_name: file.name,
    file_type: file.file_type,
    category: file.category,
    path: file.path,
    size: Number.isFinite(size) ? size : null,
    modified: file.modified,
    tags: [],
    score: 0,
    metadata: null,
    chunks: null,
  };
}

export function useRecentAccess(client: ApiClient = defaultClient) {
  const t = useTranslate();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const pageSize = 20;

  const query = useQuery({
    queryKey: [...RECENT_LIST_QUERY_KEY, page, pageSize] as const,
    queryFn: async (): Promise<RecentPageData> => {
      const response = await listRecent(page, pageSize, client);
      if (response.status !== "success" || !response.data) {
        throw new Error(errorText(response.error) || t("recent.loadFailed", "加载最近访问失败"));
      }

      const data = response.data;
      return {
        items: data.items.map((item) => ({
          recordId: item.id,
          fileId: item.file_id,
          accessedAt: item.accessed_at,
          file: toRecentFile(item.file_id, item.accessed_at, item.file),
        })),
        pageNumber: data.page_number,
        pageSize: data.page_size,
        total: data.total,
        hasMore: data.has_more,
      };
    },
  });

  const deleteRecords = useMutation({
    mutationFn: async (recordIds: number[]): Promise<RecentDeleteResult> => {
      const result: RecentDeleteResult = {
        successCount: 0,
        failureCount: 0,
        failedRecordIds: [],
        errors: [],
      };

      for (const recordId of recordIds) {
        try {
          const response = await deleteRecentRecord(recordId, client);
          if (response.status === "success") {
            result.successCount += 1;
          } else {
            result.failureCount += 1;
            result.failedRecordIds.push(recordId);
            result.errors.push(errorText(response.error) || t("recent.deleteFailed", "删除访问记录失败"));
          }
        } catch (error) {
          result.failureCount += 1;
          result.failedRecordIds.push(recordId);
          result.errors.push(error instanceof Error ? error.message : t("recent.deleteFailed", "删除访问记录失败"));
        }
      }

      return result;
    },
    onSuccess: (result) => {
      if (result.successCount > 0) {
        void queryClient.invalidateQueries({ queryKey: RECENT_LIST_QUERY_KEY });
      }
    },
  });

  return {
    data: query.data,
    loading: query.isPending,
    error: query.error instanceof Error ? query.error.message : null,
    page,
    setPage,
    pageSize,
    reload: () => queryClient.invalidateQueries({ queryKey: RECENT_LIST_QUERY_KEY }),
    deleteRecords,
  };
}
