import { useMutation, useQueryClient } from "@tanstack/react-query";

import { defaultClient, type ApiClient } from "../../../services/api/client";
import { addRecent } from "../../../services/api/recent";

const RECENT_LIST_QUERY_KEY = ["recent", "list"] as const;

export function useRecordRecentAccess(client: ApiClient = defaultClient) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (fileId: string) => addRecent(fileId, client),
    onSuccess: (response) => {
      if (response.status === "success") {
        void queryClient.invalidateQueries({ queryKey: RECENT_LIST_QUERY_KEY });
      }
      return response;
    },
  });
}
