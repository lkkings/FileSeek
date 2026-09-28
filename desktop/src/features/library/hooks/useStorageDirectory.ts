import { useQuery } from "@tanstack/react-query";

import { defaultClient, errorText, type ApiClient } from "../../../services/api/client";
import { listStorageDirectory } from "../../../services/api/settings";
import { useTranslate } from "../../../i18n/useTranslate";

export function useStorageDirectory(
  storageId: string | null,
  path: string,
  client: ApiClient = defaultClient,
) {
  const t = useTranslate();
  const query = useQuery({
    queryKey: ["library", "storage-directory", storageId, path],
    enabled: Boolean(storageId),
    queryFn: async () => {
      const response = await listStorageDirectory(storageId ?? "", path, client);
      if (response.status !== "success" || !response.data) {
        throw new Error(
          errorText(response.error) || t("import.directoryLoadFailed", "无法读取目录"),
        );
      }
      return response.data;
    },
  });

  return {
    entries: query.data?.entries ?? [],
    currentPath: query.data?.current_path ?? "",
    loading: query.isPending,
    error: query.error instanceof Error ? query.error.message : null,
    retry: () => void query.refetch(),
  };
}
