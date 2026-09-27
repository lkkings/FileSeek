import { useMutation } from "@tanstack/react-query";
import { useCallback, useMemo, useState } from "react";
import { searchFiles } from "../../../services/api/search";
import type { SearchRequest } from "../../../services/api/search";
import { defaultClient, errorText, type ApiClient } from "../../../services/api/client";
import { useTranslate } from "../../../i18n/useTranslate";
import type { FileType, SearchFilterKey, SearchFilters } from "../types";

type SearchSubmitResult = { ok: true; resultCount: number } | { ok: false; message: string };

const initialFilters: SearchFilters = {
  globalQuery: "",
  nameQuery: "",
  fileType: "all",
  minSize: "",
  maxSize: "",
  startDate: "",
  endDate: "",
};

export function useFileSearch(client: ApiClient = defaultClient) {
  const t = useTranslate();
  const [filters, setFilters] = useState<SearchFilters>(initialFilters);
  const [validationError, setValidationError] = useState<string | null>(null);
  const searchMutation = useMutation({ mutationFn: (request: SearchRequest) => searchFiles(request, client) });

  const updateFilter = useCallback(<Key extends SearchFilterKey>(key: Key, value: SearchFilters[Key]) => {
    setFilters((current) => ({ ...current, [key]: value }));
  }, []);

  const resetFilters = useCallback(() => setFilters(initialFilters), []);

  const folderQuery = useMemo(() => [filters.globalQuery, filters.nameQuery].filter(Boolean).join(" ").trim().toLowerCase(), [filters.globalQuery, filters.nameQuery]);
  const matchesFolder = useCallback((folderName: string) => !folderQuery || folderName.toLowerCase().includes(folderQuery), [folderQuery]);

  const submitSearch = useCallback(async (
    folderId: string | null = null,
    sortBy: "relevance" | "created_at" | "size" = "relevance",
    sortOrder: "asc" | "desc" = "desc",
    fileTypeOverride?: FileType,
  ): Promise<SearchSubmitResult> => {
    const query = filters.globalQuery.trim();
    if (!query) {
      const error = t("search.queryRequired", "请输入搜索关键词");
      setValidationError(error);
      return { ok: false, message: error };
    }

    const fileType = fileTypeOverride ?? filters.fileType;
    const categories = fileType === "all" ? ["document", "image", "video"] : [fileType];
    const toNumber = (value: string) => {
      if (!value.trim()) return null;
      const parsed = Number(value);
      return Number.isFinite(parsed) && parsed >= 0 ? parsed : null;
    };

    setValidationError(null);
    searchMutation.reset();
    const response = await searchMutation.mutateAsync({
      query,
      categories,
      page_size: 20,
      page_number: 1,
      folder_id: folderId,
      sort_by: sortBy,
      sort_order: sortOrder,
      name_query: filters.nameQuery.trim() || null,
      min_size_m: toNumber(filters.minSize),
      max_size_m: toNumber(filters.maxSize),
      start_date: filters.startDate || null,
      end_date: filters.endDate || null,
    });

    if (response.status !== "success" || !response.data) {
      const error = errorText(response.error) || t("search.failed", "搜索失败");
      return { ok: false, message: error };
    }

    const resultCount = response.data.items.length;
    return { ok: true, resultCount };
  }, [filters, searchMutation, t]);

  const searchState = {
    status: validationError ? "error" as const : searchMutation.isPending ? "loading" as const : searchMutation.data?.status === "success" ? "success" as const : searchMutation.data?.status === "error" || searchMutation.isError ? "error" as const : "idle" as const,
    resultCount: searchMutation.data?.data ? searchMutation.data.data.items.length : 0,
    data: searchMutation.data?.status === "success" ? searchMutation.data.data : undefined,
    error: validationError ?? (searchMutation.data?.status === "error" ? errorText(searchMutation.data.error) : searchMutation.error instanceof Error ? searchMutation.error.message : null),
  };

  return { filters, updateFilter, resetFilters, matchesFolder, searchState, submitSearch };
}
