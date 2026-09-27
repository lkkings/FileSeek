import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { useTranslate } from "../../../i18n/useTranslate";
import { defaultClient, errorText, type ApiClient } from "../../../services/api/client";
import { deleteRecycleBatch, listRecycle, restoreRecycleBatch } from "../../../services/api/recycle";

const RECYCLE_LIST_QUERY_KEY = ["recycle", "list"] as const;

export function useRecycleBin(client: ApiClient = defaultClient) {
  const t = useTranslate();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const pageSize = 20;

  const query = useQuery({
    queryKey: [...RECYCLE_LIST_QUERY_KEY, page, pageSize] as const,
    queryFn: async () => {
      const response = await listRecycle(page, pageSize, client);
      if (response.status !== "success" || !response.data) {
        throw new Error(errorText(response.error) || t("recycle.loadFailed", "加载回收站失败"));
      }
      return response.data;
    },
  });

  const deleteRecords = useMutation({
    mutationFn: (itemIds: string[]) => deleteRecycleBatch(itemIds, client),
    onSuccess: (response) => {
      if (response.status === "success") {
        void queryClient.invalidateQueries({ queryKey: RECYCLE_LIST_QUERY_KEY });
      }
      return response;
    },
  });

  const restoreRecords = useMutation({
    mutationFn: (itemIds: string[]) => restoreRecycleBatch(itemIds, client),
    onSuccess: (response) => {
      if (response.status === "success") {
        void queryClient.invalidateQueries({ queryKey: RECYCLE_LIST_QUERY_KEY });
      }
      return response;
    },
  });

  return {
    data: query.data,
    loading: query.isPending,
    error: query.error instanceof Error ? query.error.message : null,
    page,
    setPage,
    pageSize,
    reload: () => queryClient.invalidateQueries({ queryKey: RECYCLE_LIST_QUERY_KEY }),
    deleteRecords,
    restoreRecords,
  };
}
