import { useMutation, useQueryClient } from "@tanstack/react-query";

import { defaultClient, type ApiClient } from "../../../services/api/client";
import { addFilesToRecycle } from "../../../services/api/recycle";

const RECYCLE_LIST_QUERY_KEY = ["recycle", "list"] as const;

export function useMoveFilesToRecycle(client: ApiClient = defaultClient) {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: (fileIds: string[]) => addFilesToRecycle(fileIds, client),
    onSuccess: (response) => {
      if (response.status === "success") {
        void queryClient.invalidateQueries({ queryKey: RECYCLE_LIST_QUERY_KEY });
      }
      return response;
    },
  });

  return mutation;
}
