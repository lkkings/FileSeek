import { useMutation } from "@tanstack/react-query";
import { useCallback, useMemo, useState } from "react";
import { searchFiles } from "../../../services/api/search";
import type { SearchRequest } from "../../../services/api/search";
import { defaultClient, errorText, type ApiClient } from "../../../services/api/client";
import { useTranslate } from "../../../i18n/useTranslate";
import type { FileType, SearchFilterKey, SearchFilters } from "../types";

type SearchSubmitResult = { ok: true; resultCount: number } | { ok: false; message: string };
type SearchSortBy = SearchRequest["sort_by"];
type SearchSortOrder = SearchRequest["sort_order"];

interface SearchSubmitOptions {
  folderId?: string | null;
  pageNumber?: number;
  pageSize?: number;
  sortBy?: SearchSortBy;
  sortOrder?: SearchSortOrder;
  fileTypeOverride?: FileType;
}

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
  const [pageNumber, setPageNumber] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [sortBy, setSortBy] = useState<SearchSortBy>("relevance");
  const [sortOrder, setSortOrder] = useState<SearchSortOrder>("desc");
  const [validationError, setValidationError] = useState<string | null>(null);
  const searchMutation = useMutation({ mutationFn: (request: SearchRequest) => searchFiles(request, client) });

  const updateFilter = useCallback(<Key extends SearchFilterKey>(key: Key, value: SearchFilters[Key]) => {
    setFilters((current) => ({ ...current, [key]: value }));
  }, []);

  const resetFilters = useCallback(() => {
    setFilters(initialFilters);
    setPageNumber(1);
  }, []);

  const folderQuery = useMemo(() => [filters.globalQuery, filters.nameQuery].filter(Boolean).join(" ").trim().toLowerCase(), [filters.globalQuery, filters.nameQuery]);
  const matchesFolder = useCallback((folderName: string) => !folderQuery || folderName.toLowerCase().includes(folderQuery), [folderQuery]);

  const submitSearch = useCallback(async ({
    folderId = null,
    pageNumber: nextPageNumber = pageNumber,
    pageSize: nextPageSize = pageSize,
    sortBy: nextSortBy = sortBy,
    sortOrder: nextSortOrder = sortOrder,
    fileTypeOverride,
  }: SearchSubmitOptions = {}): Promise<SearchSubmitResult> => {
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
    const request: SearchRequest = {
      query,
      categories,
      page_size: nextPageSize,
      page_number: nextPageNumber,
      folder_id: folderId,
      sort_by: nextSortBy,
      sort_order: nextSortOrder,
      name_query: filters.nameQuery.trim() || null,
      min_size_m: toNumber(filters.minSize),
      max_size_m: toNumber(filters.maxSize),
      start_date: filters.startDate || null,
      end_date: filters.endDate || null,
    };
    let response = await searchMutation.mutateAsync(request);
    let finalPageNumber = nextPageNumber;

    if (
      response.status === "success" &&
      response.data &&
      response.data.items.length === 0 &&
      nextPageNumber > 1
    ) {
      const closestValidPage = Math.max(1, Math.ceil(response.data.total / response.data.page_size));
      if (closestValidPage < nextPageNumber) {
        response = await searchMutation.mutateAsync({ ...request, page_number: closestValidPage });
        finalPageNumber = closestValidPage;
      }
    }

    if (response.status !== "success" || !response.data) {
      const error = errorText(response.error) || t("search.failed", "搜索失败");
      return { ok: false, message: error };
    }

    setPageNumber(finalPageNumber);
    setPageSize(nextPageSize);
    setSortBy(nextSortBy);
    setSortOrder(nextSortOrder);
    const resultCount = response.data.total;
    return { ok: true, resultCount };
  }, [filters, pageNumber, pageSize, searchMutation, sortBy, sortOrder, t]);

  const changePage = useCallback((nextPage: number) => {
    if (nextPage < 1) return Promise.resolve({ ok: false, message: "" } as SearchSubmitResult);
    return submitSearch({ pageNumber: nextPage });
  }, [submitSearch]);

  const changeSorting = useCallback((nextSortBy: SearchSortBy, nextSortOrder: SearchSortOrder) => {
    return submitSearch({ pageNumber: 1, sortBy: nextSortBy, sortOrder: nextSortOrder });
  }, [submitSearch]);

  const searchState = {
    status: validationError ? "error" as const : searchMutation.isPending ? "loading" as const : searchMutation.data?.status === "success" ? "success" as const : searchMutation.data?.status === "error" || searchMutation.isError ? "error" as const : "idle" as const,
    resultCount: searchMutation.data?.data ? searchMutation.data.data.total : 0,
    pageNumber: searchMutation.data?.data?.page_number ?? pageNumber,
    pageSize: searchMutation.data?.data?.page_size ?? pageSize,
    sortBy,
    sortOrder,
    data: searchMutation.data?.status === "success" ? searchMutation.data.data : undefined,
    error: validationError ?? (searchMutation.data?.status === "error" ? errorText(searchMutation.data.error) : searchMutation.error instanceof Error ? searchMutation.error.message : null),
  };

  return {
    filters,
    updateFilter,
    resetFilters,
    matchesFolder,
    searchState,
    submitSearch,
    changePage,
    changeSorting,
  };
}
