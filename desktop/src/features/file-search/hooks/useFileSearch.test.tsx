import { act, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ApiClient, type RawResponse } from "../../../services/api/client";
import type { EnhancedSearchEventStreamTransport } from "../../../services/api/enhanced-search-events";
import type { SearchResponseData } from "../../../services/api/search";
import { useFileSearch } from "./useFileSearch";
import { renderHookWithProviders } from "../../../test/test-utils";

const responseData: SearchResponseData = {
  items: [],
  total: 0,
  page_number: 1,
  page_size: 20,
  has_more: false,
  counter: {},
};

function createTransport(agentConfigured = true) {
  return vi.fn(
    async (method: string, path: string, body?: string): Promise<RawResponse> => {
      if (method === "GET" && path === "/api/v1/settings/agent") {
        return {
          status: 200,
          body: JSON.stringify({
            status: "success",
            data: {
              base_url: "https://api.example.com/v1",
              model: "retrieval-expert",
              api_key_configured: agentConfigured,
            },
            error: null,
          }),
        };
      }
      return {
        status: 200,
        body: JSON.stringify({
          status: "success",
          data: { ...responseData, total: body ? 21 : 0 },
          error: null,
        }),
      };
    },
  );
}

function postCalls(transport: ReturnType<typeof createTransport>) {
  return transport.mock.calls.filter(([method]) => method === "POST");
}

function progressFrame(payload: object) {
  return `event: progress\ndata: ${JSON.stringify(payload)}\n\n`;
}

function createStreamTransport() {
  const calls: Array<{ path: string; request: object }> = [];
  const transport: EnhancedSearchEventStreamTransport = {
    async open(path, request, onChunk) {
      calls.push({ path, request });
      onChunk(progressFrame({ type: "status", phase: "starting" }));
      onChunk(
        progressFrame({
          type: "result",
          result: {
            items: [],
            total: 21,
            page_number: 1,
            page_size: 20,
            has_more: true,
            counter: {},
          },
        }),
      );
    },
  };
  return { transport, calls };
}

describe("useFileSearch", () => {
  it("submits a folder-scoped advanced search request", async () => {
    const transport = createTransport();
    const client = new ApiClient(transport);
    const { result } = renderHookWithProviders(() => useFileSearch(client));

    await waitFor(() => expect(result.current.agentSettingsConfigured).toBe(true));
    act(() => {
      result.current.updateFilter("globalQuery", "旅游");
    });
    let response: Awaited<ReturnType<typeof result.current.submitSearch>>;
    await act(async () => {
      response = await result.current.submitSearch({ folderId: "folder-1" });
    });

    expect(response.ok).toBe(true);
    const calls = postCalls(transport);
    expect(calls).toHaveLength(1);
    expect(calls[0][1]).toBe("/api/v1/search");
    const requestBody = JSON.parse(calls[0][2]) as {
      query: string;
      folder_id: string;
      page_number: number;
      page_size: number;
      sort_by: string;
      sort_order: string;
    };
    expect(requestBody.query).toBe("旅游");
    expect(requestBody.folder_id).toBe("folder-1");
    expect(requestBody.page_number).toBe(1);
    expect(requestBody.page_size).toBe(20);
    expect(requestBody.sort_by).toBe("relevance");
    expect(requestBody.sort_order).toBe("desc");
  });

  it("requests a selected page with unchanged filters and current sorting", async () => {
    const transport = createTransport();
    const client = new ApiClient(transport);
    const { result } = renderHookWithProviders(() => useFileSearch(client));

    await waitFor(() => expect(result.current.agentSettingsConfigured).toBe(true));
    act(() => {
      result.current.updateFilter("globalQuery", "旅游");
    });
    await act(async () => {
      await result.current.changeSorting("created_at", "asc");
    });
    await act(async () => {
      await result.current.changePage(2);
    });

    const calls = postCalls(transport);
    expect(calls).toHaveLength(2);
    const requestBody = JSON.parse(calls[1][2]) as {
      query: string;
      page_number: number;
      page_size: number;
      sort_by: string;
      sort_order: string;
    };
    expect(requestBody.query).toBe("旅游");
    expect(requestBody.page_number).toBe(2);
    expect(requestBody.page_size).toBe(20);
    expect(requestBody.sort_by).toBe("created_at");
    expect(requestBody.sort_order).toBe("asc");
  });

  it("submits initial retrieval-augmented searches to the stream endpoint", async () => {
    const transport = createTransport();
    const client = new ApiClient(transport);
    const stream = createStreamTransport();
    const { result } = renderHookWithProviders(() =>
      useFileSearch(client, { streamTransport: stream.transport }),
    );

    await waitFor(() => expect(result.current.agentSettingsConfigured).toBe(true));
    act(() => {
      result.current.setSearchMode("enhanced");
      result.current.updateFilter("globalQuery", "上个月旅行的猫照片");
    });
    let response: Awaited<ReturnType<typeof result.current.submitSearch>>;
    await act(async () => {
      response = await result.current.submitSearch({ folderId: "folder-1" });
    });

    expect(response.ok).toBe(true);
    expect(stream.calls).toHaveLength(1);
    expect(stream.calls[0].path).toBe("/api/v1/search/enhanced/stream");
    expect(stream.calls[0].request).toEqual({
      query: "上个月旅行的猫照片",
      folder_id: "folder-1",
      page_number: 1,
      page_size: 20,
      sort_by: "relevance",
      sort_order: "desc",
    });
    expect(postCalls(transport)).toHaveLength(0);
    expect(result.current.searchState.status).toBe("success");
    expect(result.current.searchState.data?.total).toBe(21);
    expect(result.current.searchState.progressEvents).toEqual([
      { type: "status", phase: "starting" },
    ]);
  });

  it("blocks enhanced search when the agent is not configured", async () => {
    const transport = createTransport(false);
    const client = new ApiClient(transport);
    const { result } = renderHookWithProviders(() => useFileSearch(client));

    await waitFor(() => expect(result.current.agentSettingsConfigured).toBe(false));
    act(() => {
      result.current.setSearchMode("enhanced");
      result.current.updateFilter("globalQuery", "猫照片");
    });
    let response: Awaited<ReturnType<typeof result.current.submitSearch>>;
    await act(async () => {
      response = await result.current.submitSearch();
    });

    expect(response.ok).toBe(false);
    expect(response.message).toBe("请先在系统设置中配置检索智能体");
    expect(postCalls(transport)).toHaveLength(0);
    expect(result.current.searchState.error).toBe("请先在系统设置中配置检索智能体");
  });

  it("ignores late events from a superseded enhanced search", async () => {
    const transport = createTransport();
    const client = new ApiClient(transport);
    const calls: Array<{ path: string; request: object }> = [];
    let releaseFirst: (() => void) | undefined;
    const streamTransport: EnhancedSearchEventStreamTransport = {
      async open(path, request, onChunk) {
        calls.push({ path, request });
        if (calls.length === 1) {
          await new Promise<void>((resolve) => {
            releaseFirst = resolve;
          });
          onChunk(progressFrame({ type: "status", phase: "stale" }));
          onChunk(
            progressFrame({
              type: "result",
              result: {
                items: [],
                total: 99,
                page_number: 1,
                page_size: 20,
                has_more: false,
                counter: {},
              },
            }),
          );
          return;
        }
        onChunk(progressFrame({ type: "status", phase: "current" }));
        onChunk(
          progressFrame({
            type: "result",
            result: {
              items: [],
              total: 21,
              page_number: 1,
              page_size: 20,
              has_more: true,
              counter: {},
            },
          }),
        );
      },
    };
    const { result } = renderHookWithProviders(() =>
      useFileSearch(client, { streamTransport }),
    );

    await waitFor(() => expect(result.current.agentSettingsConfigured).toBe(true));
    act(() => {
      result.current.setSearchMode("enhanced");
      result.current.updateFilter("globalQuery", "第一次搜索");
    });
    let firstSearch: Promise<{ ok: boolean; message?: string }>;
    act(() => {
      firstSearch = result.current.submitSearch();
    });
    await act(async () => {
      await Promise.resolve();
    });
    act(() => {
      result.current.updateFilter("globalQuery", "第二次搜索");
    });
    await act(async () => {
      const secondSearch = result.current.submitSearch();
      await secondSearch;
    });
    releaseFirst?.();
    await act(async () => {
      await firstSearch;
    });

    expect(result.current.searchState.status).toBe("success");
    expect(result.current.searchState.data?.total).toBe(21);
    expect(result.current.searchState.progressEvents).toEqual([
      { type: "status", phase: "current" },
    ]);
  });

  it("closes an enhanced stream when the hook unmounts", async () => {
    const transport = createTransport();
    const client = new ApiClient(transport);
    const signals: AbortSignal[] = [];
    const streamTransport: EnhancedSearchEventStreamTransport = {
      async open(path, request, onChunk, signal) {
        signals.push(signal);
        await new Promise<void>((resolve) => signal.addEventListener("abort", resolve, { once: true }));
        onChunk(progressFrame({ type: "status", phase: "late" }));
      },
    };
    const { result, unmount } = renderHookWithProviders(() =>
      useFileSearch(client, { streamTransport }),
    );

    await waitFor(() => expect(result.current.agentSettingsConfigured).toBe(true));
    act(() => {
      result.current.setSearchMode("enhanced");
      result.current.updateFilter("globalQuery", "猫照片");
    });
    let search: Promise<{ ok: boolean; message?: string }>;
    act(() => {
      search = result.current.submitSearch();
    });
    unmount();
    await act(async () => {
      await search;
    });

    expect(signals[0]?.aborted).toBe(true);
  });

  it("uses the non-streaming enhanced endpoint for sorting and pagination", async () => {
    const transport = createTransport();
    const client = new ApiClient(transport);
    const stream = createStreamTransport();
    const { result } = renderHookWithProviders(() =>
      useFileSearch(client, { streamTransport: stream.transport }),
    );

    await waitFor(() => expect(result.current.agentSettingsConfigured).toBe(true));
    act(() => {
      result.current.setSearchMode("enhanced");
      result.current.updateFilter("globalQuery", "猫照片");
    });
    await act(async () => {
      await result.current.submitSearch();
    });
    await act(async () => {
      await result.current.changeSorting("created_at", "asc");
    });
    await act(async () => {
      await result.current.changePage(2);
    });

    const calls = postCalls(transport);
    expect(stream.calls).toHaveLength(1);
    expect(calls).toHaveLength(2);
    expect(calls.every(([method, path]) => method === "POST" && path === "/api/v1/search/enhanced")).toBe(true);
    expect(JSON.parse(calls[0][2]).page_number).toBe(1);
    expect(JSON.parse(calls[1][2]).page_number).toBe(2);
    expect(result.current.searchState.data?.total).toBe(21);
  });
});
