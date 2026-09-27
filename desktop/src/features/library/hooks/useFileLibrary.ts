import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFolder as createFolderRequest, deleteFolder as deleteFolderRequest, listFolders, updateFolder as updateFolderRequest } from "../../../services/api/library";
import { defaultClient, errorText, type ApiClient } from "../../../services/api/client";
import { useTranslate } from "../../../i18n/useTranslate";
import type { FolderFormValues, FolderRecord } from "../types";

function toFolderRecord(folder: { id: string; name: string; iconType: string; description: string; modified: string; file_count: number }): FolderRecord {
  return { id: folder.id, name: folder.name, iconType: folder.iconType, description: folder.description, modified: folder.modified, fileCount: folder.file_count };
}

export function useFileLibrary(client: ApiClient = defaultClient) {
  const t = useTranslate();
  const queryClient = useQueryClient();
  const folderQueryKey = ["library", "folders"] as const;

  const foldersQuery = useQuery({
    queryKey: folderQueryKey,
    queryFn: async () => {
      const response = await listFolders(client);
      if (response.status !== "success" || !response.data) {
        throw new Error(errorText(response.error) || t("library.loadFailed", "无法读取文件夹列表"));
      }
      return response.data.map(toFolderRecord);
    },
  });

  const createMutation = useMutation({
    mutationFn: async (input: FolderFormValues) => {
      const response = await createFolderRequest({ name: input.name.trim(), iconType: input.iconType, description: input.description.trim() }, client);
      if (response.status !== "success") throw new Error(errorText(response.error) || t("folder.createFailed", "创建文件夹失败"));
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: folderQueryKey }),
  });

  const updateMutation = useMutation({
    mutationFn: async ({ folderId, input }: { folderId: string; input: FolderFormValues }) => {
      const response = await updateFolderRequest(folderId, { name: input.name.trim(), iconType: input.iconType, description: input.description.trim() }, client);
      if (response.status !== "success") throw new Error(errorText(response.error) || t("folder.updateFailed", "保存文件夹失败"));
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: folderQueryKey }),
  });

  const deleteMutation = useMutation({
    mutationFn: async (folderId: string) => {
      const response = await deleteFolderRequest(folderId, client);
      if (response.status !== "success") throw new Error(errorText(response.error) || t("folder.deleteFailed", "删除文件夹失败"));
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: folderQueryKey }),
  });

  const reload = () => queryClient.invalidateQueries({ queryKey: folderQueryKey });

  async function runMutation(action: () => Promise<void>) {
    try {
      await action();
      return null;
    } catch (cause) {
      return cause instanceof Error ? cause.message : t("library.operationFailed", "操作未完成");
    }
  }

  return {
    folders: foldersQuery.data ?? [],
    loading: foldersQuery.isPending,
    error: foldersQuery.error instanceof Error ? foldersQuery.error.message : null,
    reload,
    createFolder: (input: FolderFormValues) => runMutation(() => createMutation.mutateAsync(input)),
    updateFolder: (folderId: string, input: FolderFormValues) => runMutation(() => updateMutation.mutateAsync({ folderId, input })),
    deleteFolder: (folderId: string) => runMutation(() => deleteMutation.mutateAsync(folderId)),
  };
}
