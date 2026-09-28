import { useQuery } from "@tanstack/react-query";

import { defaultClient, errorText, type ApiClient } from "../../../services/api/client";
import { listTags } from "../../../services/api/library";
import { useTranslate } from "../../../i18n/useTranslate";

export const DEFAULT_LIBRARY_TAGS = ["文档", "图片", "视频"] as const;

export function useLibraryTags(client: ApiClient = defaultClient, enabled = true) {
  const t = useTranslate();

  const query = useQuery({
    queryKey: ["library", "tags"],
    queryFn: async () => {
      const response = await listTags(client);
      if (response.status !== "success" || !response.data) {
        throw new Error(errorText(response.error) || t("library.tagsLoadFailed", "无法读取标签列表"));
      }
      return response.data;
    },
    enabled,
  });

  return {
    tags: query.isError ? [...DEFAULT_LIBRARY_TAGS] : query.data ?? [],
    loading: query.isPending,
    error: query.error instanceof Error ? query.error.message : null,
    refetch: query.refetch,
  };
}
