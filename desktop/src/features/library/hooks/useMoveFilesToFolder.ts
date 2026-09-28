import { useMutation, useQueryClient } from "@tanstack/react-query";

import { defaultClient, type ApiClient } from "../../../services/api/client";
import { moveFilesToFolder } from "../../../services/api/library";

const LIBRARY_FOLDERS_QUERY_KEY = ["library", "folders"] as const;

export function useMoveFilesToFolder(client: ApiClient = defaultClient) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (input: { fileIds: string[]; targetFolderId: string }) =>
      moveFilesToFolder(input, client),
    onSuccess: (response) => {
      if (response.status === "success") {
        void queryClient.invalidateQueries({ queryKey: LIBRARY_FOLDERS_QUERY_KEY });
      }
      return response;
    },
  });
}
