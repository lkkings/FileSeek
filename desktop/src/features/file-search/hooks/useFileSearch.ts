import { useMutation, useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useTranslate } from "../../../i18n/useTranslate";
import { defaultClient, errorText, type ApiClient } from "../../../services/api/client";
import {
  openEnhancedSearchEventStream,
  type EnhancedSearchEventStreamTransport,
} from "../../../services/api/enhanced-search-events";
import { getAgentSettings } from "../../../services/api/settings";
import { enhancedSearchFiles, searchFiles } from "../../../services/api/search";
import type {
  EnhancedSearchProgressEvent,
  EnhancedSearchRequest,
  SearchResponseData,
  SearchRequest,
} from "../../../services/api/search";
import type { FileType, SearchFilterKey, SearchFilters, SearchMode } from "../types";

type SearchSubmitResult = { ok: true; resultCount: number } | { ok: false; message: string };
type SearchSortBy = SearchRequest["sort_by"];
type SearchSortOrder = SearchRequest["sort_order"];
type SearchStatus = "idle" | "loading" | "success" | "error";

interface SearchSubmitOptions {
  folderId?: string | null;
  pageNumber?: number;
  pageSize?: number;
  sortBy?: SearchSortBy;
  sortOrder?: SearchSortOrder;
  fileTypeOverride?: FileType;
  useStream?: boolean;
}

interface UseFileSearchOptions {
  streamTransport?: EnhancedSearchEventStreamTransport;
}

interface EnhancedSearchStreamState {
  status: SearchStatus;
  events: EnhancedSearchProgressEvent[];
  data?: SearchResponseData;
  error?: string | null;
}

type SearchMutationInput =
  | { mode: "advanced"; request: SearchRequest }
  | { mode: "enhanced"; request: EnhancedSearchRequest };

const initialFilters: SearchFilters = {
  globalQuery: "",
  nameQuery: "",
  fileType: "all",
  minSize: "",
  maxSize: "",
  startDate: "",
  endDate: "",
};

const initialEnhancedSearchState: EnhancedSearchStreamState = {
  status: "idle",
  events: [],
  error: null,
};

export function useFileSearch(
  client: ApiClient = defaultClient,
  options: UseFileSearchOptions = {},
) {
  const t = useTranslate();
  const [filters, setFilters] = useState<SearchFilters>(initialFilters);
  const [pageNumber, setPageNumber] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [sortBy, setSortBy] = useState<SearchSortBy>("relevance");
  const [sortOrder, setSortOrder] = useState<SearchSortOrder>("desc");
  const [searchMode, setSearchMode] = useState<SearchMode>("advanced");
  const [validationError, setValidationError] = useState<string | null>(null);
  const [enhancedSearchState, setEnhancedSearchState] = useState(initialEnhancedSearchState);
  const streamRef = useRef<ReturnType<typeof openEnhancedSearchEventStream> | null>(null);
  const requestSequenceRef = useRef(0);
  const searchMutation = useMutation({
    mutationFn: ({ mode, request }: SearchMutationInput) =>
      mode === "enhanced" ? enhancedSearchFiles(request, client) : searchFiles(request, client),
  });
  const agentSettingsQuery = useQuery({
    queryKey: ["settings", "agent"],
    queryFn: async () => {
      const response = await getAgentSettings(client);
      if (response.status !== "success" || !response.data) {
        throw new Error(
          errorText(response.error) ||
            t("search.agentSettingsLoadFailed", "无法读取检索智能体设置"),
        );
      }
      return response.data;
    },
  });

  useEffect(
    () => () => {
      requestSequenceRef.current += 1;
      streamRef.current?.close();
    },
    [],
  );

  const updateFilter = useCallback(
    <Key extends SearchFilterKey>(key: Key, value: SearchFilters[Key]) => {
      setFilters((current) => ({ ...current, [key]: value }));
    },
    [],
  );

  const resetFilters = useCallback(() => {
    setFilters(initialFilters);
    setPageNumber(1);
  }, []);

  const changeSearchMode = useCallback((nextMode: SearchMode) => {
    setSearchMode(nextMode);
    setValidationError(null);
    setPageNumber(1);
  }, []);

  const folderQuery = useMemo(
    () => [filters.globalQuery, filters.nameQuery].filter(Boolean).join(" ").trim().toLowerCase(),
    [filters.globalQuery, filters.nameQuery],
  );
  const matchesFolder = useCallback(
    (folderName: string) => !folderQuery || folderName.toLowerCase().includes(folderQuery),
    [folderQuery],
  );

  const submitSearch = useCallback(
    async ({
      folderId = null,
      pageNumber: nextPageNumber = pageNumber,
      pageSize: nextPageSize = pageSize,
      sortBy: nextSortBy = sortBy,
      sortOrder: nextSortOrder = sortOrder,
      fileTypeOverride,
      useStream = true,
    }: SearchSubmitOptions = {}): Promise<SearchSubmitResult> => {
      const query = filters.globalQuery.trim();
      if (!query) {
        const error = t("search.queryRequired", "请输入搜索关键词");
        setValidationError(error);
        return { ok: false, message: error };
      }

      if (
        searchMode === "enhanced" &&
        agentSettingsQuery.data?.api_key_configured !== true
      ) {
        const error = t("search.agentSettingsRequired", "请先在系统设置中配置检索智能体");
        setValidationError(error);
        return { ok: false, message: error };
      }

      const fileType = fileTypeOverride ?? filters.fileType;
      const categories =
        fileType === "all" ? ["document", "image", "video"] : [fileType];
      const toNumber = (value: string) => {
        if (!value.trim()) return null;
        const parsed = Number(value);
        return Number.isFinite(parsed) && parsed >= 0 ? parsed : null;
      };

      setValidationError(null);
      searchMutation.reset();

      if (searchMode === "enhanced" && useStream) {
        requestSequenceRef.current += 1;
        const requestSequence = requestSequenceRef.current;
        streamRef.current?.close();
        setEnhancedSearchState({
          status: "loading",
          events: [],
          error: null,
        });

        let hasResult = false;
        let resultCount = 0;
        let streamError: string | null = null;
        const stream = openEnhancedSearchEventStream(
          {
            query,
            page_size: nextPageSize,
            page_number: nextPageNumber,
            folder_id: folderId,
            sort_by: nextSortBy,
            sort_order: nextSortOrder,
          },
          {
            onEvent: (event) => {
              if (requestSequence !== requestSequenceRef.current) return;
              if (event.type === "result") {
                const result = event.result;
                if (result === null || result === undefined) {
                  streamError = t("search.enhanced.streamFailed", "检索增强搜索连接中断");
                  setEnhancedSearchState((current) => ({
                    ...current,
                    status: "error",
                    error: streamError,
                  }));
                  return;
                }
                hasResult = true;
                resultCount = result.total;
                setEnhancedSearchState((current) => ({
                  ...current,
                  status: "success",
                  data: result,
                  error: null,
                }));
                return;
              }
              if (event.type === "error") {
                streamError = event.error ?? t("search.failed", "搜索失败");
                setEnhancedSearchState((current) => ({
                  ...current,
                  status: "error",
                  error: streamError,
                }));
                return;
              }
              setEnhancedSearchState((current) => ({
                ...current,
                events: [...current.events, event],
              }));
            },
            onError: () => {
              if (requestSequence !== requestSequenceRef.current) return;
              streamError = t(
                "search.enhanced.streamFailed",
                "检索增强搜索连接中断",
              );
              setEnhancedSearchState((current) => ({
                ...current,
                status: "error",
                error: streamError,
              }));
            },
          },
          options.streamTransport === undefined ? {} : { transport: options.streamTransport },
        );
        streamRef.current = stream;
        await stream.done;

        if (requestSequence !== requestSequenceRef.current) {
          return { ok: false, message: "" };
        }
        if (streamError !== null) {
          return { ok: false, message: streamError };
        }
        if (!hasResult) {
          const error = t("search.enhanced.streamFailed", "检索增强搜索连接中断");
          setEnhancedSearchState((current) => ({
            ...current,
            status: "error",
            error,
          }));
          return { ok: false, message: error };
        }

        setPageNumber(nextPageNumber);
        setPageSize(nextPageSize);
        setSortBy(nextSortBy);
        setSortOrder(nextSortOrder);
        return { ok: true, resultCount };
      }

      if (searchMode === "enhanced") {
        setEnhancedSearchState((current) => ({
          ...current,
          status: "loading",
          error: null,
        }));
      }

      const mutationInput: SearchMutationInput =
        searchMode === "enhanced"
          ? {
              mode: "enhanced",
              request: {
                query,
                page_size: nextPageSize,
                page_number: nextPageNumber,
                folder_id: folderId,
                sort_by: nextSortBy,
                sort_order: nextSortOrder,
              },
            }
          : {
              mode: "advanced",
              request: {
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
              },
            };

      let response = await searchMutation.mutateAsync(mutationInput);
      let finalPageNumber = nextPageNumber;

      if (
        response.status === "success" &&
        response.data &&
        response.data.items.length === 0 &&
        nextPageNumber > 1
      ) {
        const closestValidPage = Math.max(
          1,
          Math.ceil(response.data.total / response.data.page_size),
        );
        if (closestValidPage < nextPageNumber) {
          response = await searchMutation.mutateAsync({
            mode: mutationInput.mode,
            request:
              mutationInput.mode === "enhanced"
                ? { ...mutationInput.request, page_number: closestValidPage }
                : { ...mutationInput.request, page_number: closestValidPage },
          });
          finalPageNumber = closestValidPage;
        }
      }

      if (response.status !== "success" || !response.data) {
        const error = errorText(response.error) || t("search.failed", "搜索失败");
        if (searchMode === "enhanced") {
          setEnhancedSearchState((current) => ({
            ...current,
            status: "error",
            error,
          }));
        }
        return { ok: false, message: error };
      }

      if (searchMode === "enhanced") {
        const responseData = response.data;
        setEnhancedSearchState((current) => ({
          ...current,
          status: "success",
          data: responseData,
          error: null,
        }));
      }

      setPageNumber(finalPageNumber);
      setPageSize(nextPageSize);
      setSortBy(nextSortBy);
      setSortOrder(nextSortOrder);
      return { ok: true, resultCount: response.data.total };
    },
    [
      agentSettingsQuery.data,
      filters,
      options.streamTransport,
      pageNumber,
      pageSize,
      searchMode,
      searchMutation,
      sortBy,
      sortOrder,
      t,
    ],
  );

  const changePage = useCallback(
    (nextPage: number) => {
      if (nextPage < 1) {
        return Promise.resolve({ ok: false, message: "" } as SearchSubmitResult);
      }
      return submitSearch({ pageNumber: nextPage, useStream: false });
    },
    [submitSearch],
  );

  const changeSorting = useCallback(
    (nextSortBy: SearchSortBy, nextSortOrder: SearchSortOrder) => {
      return submitSearch({
        pageNumber: 1,
        sortBy: nextSortBy,
        sortOrder: nextSortOrder,
        useStream: false,
      });
    },
    [submitSearch],
  );

  const mutationStatus: SearchStatus = searchMutation.isPending
    ? "loading"
    : searchMutation.data?.status === "success"
      ? "success"
      : searchMutation.data?.status === "error" || searchMutation.isError
        ? "error"
        : "idle";
  const activeStatus: SearchStatus = searchMode === "enhanced"
    ? enhancedSearchState.status
    : mutationStatus;
  const activeData = searchMode === "enhanced"
    ? enhancedSearchState.data
    : searchMutation.data?.status === "success"
      ? searchMutation.data.data
      : undefined;
  const activeError = searchMode === "enhanced"
    ? enhancedSearchState.error
    : searchMutation.data?.status === "error"
      ? errorText(searchMutation.data.error)
      : searchMutation.error instanceof Error
        ? searchMutation.error.message
        : null;

  const searchState = {
    status: validationError ? ("error" as const) : activeStatus,
    resultCount: activeData ? activeData.total : 0,
    pageNumber: activeData?.page_number ?? pageNumber,
    pageSize: activeData?.page_size ?? pageSize,
    sortBy,
    sortOrder,
    data: activeData,
    error: validationError ?? activeError ?? null,
    progressEvents: searchMode === "enhanced" ? enhancedSearchState.events : [],
  };

  return {
    searchMode,
    setSearchMode: changeSearchMode,
    agentSettingsConfigured: agentSettingsQuery.data?.api_key_configured ?? null,
    agentSettingsLoading: agentSettingsQuery.isPending,
    agentSettingsError:
      agentSettingsQuery.error instanceof Error ? agentSettingsQuery.error.message : null,
    filters,
    updateFilter,
    resetFilters,
    matchesFolder,
    searchState,
    progressEvents: searchState.progressEvents,
    submitSearch,
    changePage,
    changeSorting,
  };
}
