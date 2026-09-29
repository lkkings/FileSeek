import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  defaultSystemIntegrationStatus,
  getSystemIntegrationStatus,
  setFileManagerIntegration,
  setSilentStartup,
} from "../../../services/tauri/system-integration";

const systemIntegrationQueryKey = ["settings", "system-integration"] as const;

export function useSystemIntegration() {
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: systemIntegrationQueryKey,
    queryFn: getSystemIntegrationStatus,
  });

  const silentStartup = useMutation({
    mutationFn: setSilentStartup,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: systemIntegrationQueryKey });
    },
  });

  const fileManager = useMutation({
    mutationFn: setFileManagerIntegration,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: systemIntegrationQueryKey });
    },
  });

  return {
    status: query.data ?? defaultSystemIntegrationStatus,
    loading: query.isPending,
    error: query.error instanceof Error ? query.error.message : null,
    setSilentStartup: silentStartup,
    setFileManagerIntegration: fileManager,
  };
}
