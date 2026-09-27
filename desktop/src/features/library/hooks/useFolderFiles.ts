import { useQuery, useQueryClient } from "@tanstack/react-query";
import { searchFiles } from "../../../services/api/search";
import { defaultClient, type ApiClient } from "../../../services/api/client";

export interface FolderFilesQueryOptions {
  folderId: string;
  category?: "all" | "document" | "image" | "video";
  tag?: string | null;
  sortBy?: "relevance" | "created_at" | "size";
  sortOrder?: "asc" | "desc";
}

export function useFolderFiles(
  options: FolderFilesQueryOptions,
  client: ApiClient = defaultClient
) {
  const queryClient = useQueryClient();
  const queryKey = ["library", "folder-files", options.folderId, options.category, options.tag, options.sortBy, options.sortOrder] as const;

  const query = useQuery({
    queryKey,
    queryFn: async () => {
      // 映射 categories 参数。如果 options.category 是 'all'，不传特殊 category，让后端默认查询所有支持的 document / image / video
      const categories =
        options.category && options.category !== "all"
          ? [options.category]
          : ["document", "image", "video"];

      const tagParam = options.tag && options.tag !== "全部" ? options.tag : null;

      const response = await searchFiles(
        {
          query: "", // 留空以列出指定 folder 下的全部文件
          folder_id: options.folderId,
          sort_by: options.sortBy || "created_at",
          sort_order: options.sortOrder || "desc",
          categories,
          tag: tagParam,
          name_query: null,
          min_size_m: null,
          max_size_m: null,
          start_date: null,
          end_date: null,
        },
        client
      );

      if (response.status !== "success" || !response.data) {
        throw new Error(
          typeof response.error === "string"
            ? response.error
            : response.error?.message || "加载文件列表失败"
        );
      }

      return response.data;
    },
    enabled: !!options.folderId,
  });

  const reload = () => {
    queryClient.invalidateQueries({ queryKey: ["library", "folder-files", options.folderId] });
  };

  return {
    data: query.data,
    loading: query.isPending,
    error: query.error instanceof Error ? query.error.message : null,
    reload,
  };
}
