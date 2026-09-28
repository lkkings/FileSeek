import { act } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ApiClient, type RawResponse } from "../../../services/api/client";
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

describe("useFileSearch", () => {
  it("submits a folder-scoped search request", async () => {
    const transport = vi.fn(async (): Promise<RawResponse> => ({
      status: 200,
      body: JSON.stringify({ status: "success", data: responseData, error: null }),
    }));
    const client = new ApiClient(transport);
    const { result } = renderHookWithProviders(() => useFileSearch(client));

    act(() => {
      result.current.updateFilter("globalQuery", "旅游");
    });
    let response: Awaited<ReturnType<typeof result.current.submitSearch>>;
    await act(async () => {
      response = await result.current.submitSearch({ folderId: "folder-1" });
    });

    expect(response.ok).toBe(true);
    expect(transport).toHaveBeenCalledTimes(1);
    const requestBody = JSON.parse(transport.mock.calls[0][2]) as {
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
    const transport = vi.fn(async (): Promise<RawResponse> => ({
      status: 200,
      body: JSON.stringify({ status: "success", data: { ...responseData, page_number: 2, total: 21 }, error: null }),
    }));
    const client = new ApiClient(transport);
    const { result } = renderHookWithProviders(() => useFileSearch(client));

    act(() => {
      result.current.updateFilter("globalQuery", "旅游");
    });
    await act(async () => {
      await result.current.changeSorting("created_at", "asc");
    });
    await act(async () => {
      await result.current.changePage(2);
    });

    expect(transport).toHaveBeenCalledTimes(2);
    const requestBody = JSON.parse(transport.mock.calls[1][2]) as {
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
});
