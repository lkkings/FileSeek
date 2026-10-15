import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { defaultClient, errorText, type ApiClient } from "../../../services/api/client";
import {
  createFolderSourceBinding,
  deleteFolderSourceBinding,
  listFolderSourceBindings,
  updateFolderSourceBinding,
  type ApiFolderSourceBinding,
} from "../../../services/api/library";
import { useTranslate } from "../../../i18n/useTranslate";
import type { FolderSourceBinding, FolderSourceBindingInput } from "../types";

function toBinding(binding: ApiFolderSourceBinding): FolderSourceBinding {
  return {
    id: binding.id,
    folderId: binding.folder_id,
    storageId: binding.storage_id,
    sourcePath: binding.source_path,
    recursive: binding.recursive,
    enabled: binding.enabled,
    watchStatus: binding.watch_status as FolderSourceBinding["watchStatus"],
    lastError: binding.last_error,
    lastErrorAt: binding.last_error_at,
  };
}

export function useFolderSourceBindings(
  folderId: string,
  client: ApiClient = defaultClient,
) {
  const t = useTranslate();
  const queryClient = useQueryClient();
  const queryKey = ["library", "folder-source-bindings", folderId] as const;

  const bindingsQuery = useQuery({
    queryKey,
    enabled: folderId !== "",
    queryFn: async () => {
      const response = await listFolderSourceBindings(folderId, client);
      if (response.status !== "success" || response.data === null) {
        throw new Error(
          errorText(response.error) || t("folderSources.loadFailed", "无法读取来源绑定"),
        );
      }
      return response.data.map(toBinding);
    },
  });

  const createMutation = useMutation({
    mutationFn: async (input: FolderSourceBindingInput) => {
      const response = await createFolderSourceBinding(folderId, input, client);
      if (response.status !== "success") {
        throw new Error(
          errorText(response.error) || t("folderSources.createFailed", "创建来源绑定失败"),
        );
      }
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey }),
  });

  const updateMutation = useMutation({
    mutationFn: async ({ bindingId, input }: { bindingId: string; input: FolderSourceBindingInput }) => {
      const response = await updateFolderSourceBinding(folderId, bindingId, input, client);
      if (response.status !== "success") {
        throw new Error(
          errorText(response.error) || t("folderSources.updateFailed", "更新来源绑定失败"),
        );
      }
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey }),
  });

  const deleteMutation = useMutation({
    mutationFn: async (bindingId: string) => {
      const response = await deleteFolderSourceBinding(folderId, bindingId, client);
      if (response.status !== "success") {
        throw new Error(
          errorText(response.error) || t("folderSources.deleteFailed", "删除来源绑定失败"),
        );
      }
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey }),
  });

  async function runMutation(action: () => Promise<void>) {
    try {
      await action();
      return null;
    } catch (cause) {
      return cause instanceof Error ? cause.message : t("folderSources.operationFailed", "来源绑定操作未完成");
    }
  }

  return {
    bindings: bindingsQuery.data ?? [],
    loading: bindingsQuery.isPending,
    error: bindingsQuery.error instanceof Error ? bindingsQuery.error.message : null,
    retry: () => void bindingsQuery.refetch(),
    createBinding: (input: FolderSourceBindingInput) =>
      runMutation(() => createMutation.mutateAsync(input)),
    updateBinding: (bindingId: string, input: FolderSourceBindingInput) =>
      runMutation(() => updateMutation.mutateAsync({ bindingId, input })),
    deleteBinding: (bindingId: string) =>
      runMutation(() => deleteMutation.mutateAsync(bindingId)),
  };
}
