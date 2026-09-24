import { useState, useCallback, useEffect, useRef } from "react";
import { type SearchResults, EMPTY_RESULTS } from "./types";
import { defaultClient, errorText, type ApiClient } from "../../api/client";

/**
 * Drives `POST /api/v1/search`.
 *
 * The endpoint returns the top N hits per media type in one shot — no page number, no
 * "has more" flags — so this hook has no `loadMore`. Raising `limit` is the only way to
 * see more, and the UI does not currently expose that.
 */

/** How many hits the backend returns per media type. Its own default is the same. */
const DEFAULT_LIMIT = 20;

const ALL_MEDIA_TYPES = ["document", "image", "video"];

export interface AdvancedSearchOptions {
  name_query?: string | undefined;
  /** Megabytes. The backend converts to bytes itself (`min_size_m` / `max_size_m`). */
  min_size_m?: number | null;
  max_size_m?: number | null;
  start_date?: string | null | undefined;
  end_date?: string | null | undefined;
}

export interface SearchState {
  busy: boolean;
  error: string | null;
  query: string | null;
  results: SearchResults;
  mediaTypes: string[];
  options?: AdvancedSearchOptions;
}

export function useSearch(injectableClient?: ApiClient) {
  const client = injectableClient || defaultClient;
  const requestVersion = useRef(0);
  const mounted = useRef(true);

  useEffect(() => () => {
    mounted.current = false;
    requestVersion.current += 1;
  }, []);

  const [state, setState] = useState<SearchState>({
    busy: false,
    error: null,
    query: null,
    results: EMPTY_RESULTS,
    mediaTypes: ALL_MEDIA_TYPES,
    options: {},
  });

  const search = useCallback(
    async (
      query: string,
      mediaTypes: string[] = ALL_MEDIA_TYPES,
      options: AdvancedSearchOptions = {},
    ) => {
      const version = ++requestVersion.current;
      setState((prev) => ({
        ...prev,
        busy: true,
        error: null,
        query,
        mediaTypes,
        options,
      }));

      try {
        const response = await client.post<SearchResults>("/search", {
          query,
          file_types: mediaTypes,
          limit: DEFAULT_LIMIT,
          ...options,
        });

        if (!mounted.current || version !== requestVersion.current) return;

        if (response.status === "success" && response.data) {
          setState((prev) => ({
            ...prev,
            busy: false,
            results: response.data,
          }));
        } else {
          setState((prev) => ({
            ...prev,
            busy: false,
            // Search reports errors as `{code, message}`, unlike every other endpoint;
            // `errorText` flattens both shapes so this never renders "[object Object]".
            error: errorText(response.error) || "搜索失败，发生未知错误。",
            results: EMPTY_RESULTS,
          }));
        }
      } catch (err) {
        if (!mounted.current || version !== requestVersion.current) return;
        const error = err as { message?: string };
        setState((prev) => ({
          ...prev,
          busy: false,
          error: error.message || "无法连接到索引服务。请确认后端是否正常启动。",
          results: EMPTY_RESULTS,
        }));
      }
    },
    [client],
  );

  return {
    state,
    search,
  };
}
