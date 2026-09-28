import { waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ApiClient, type RawResponse } from "../../../services/api/client";
import { useRecentAccess } from "./useRecentAccess";
import { useRecordRecentAccess } from "./useRecordRecentAccess";
import { renderHookWithProviders } from "../../../test/test-utils";

function createClient(response: object) {
  const transport = vi.fn(async (): Promise<RawResponse> => ({
    status: 200,
    body: JSON.stringify({ status: "success", data: response, error: null }),
  }));
  return { client: new ApiClient(transport), transport };
}

const recentList = {
  items: [
    {
      id: 42,
      file_id: "file-42",
      accessed_at: "2026-09-28T08:00:00Z",
      file: {
        id: "file-42",
        name: "Recent.pdf",
        file_type: "pdf",
        category: "document",
        size: "1048576",
        modified: "2026-09-27T08:00:00Z",
        folder_id: null,
        path: "/documents/Recent.pdf",
      },
    },
  ],
  page_number: 1,
  page_size: 20,
  total: 1,
  has_more: false,
};

describe("useRecentAccess", () => {
  it("maps backend records to UI rows while retaining record IDs", async () => {
    const { client } = createClient(recentList);
    const { result } = renderHookWithProviders(() => useRecentAccess(client));

    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(result.current.data?.items[0]?.recordId).toBe(42);
    expect(result.current.data?.items[0]?.file.file_id).toBe("file-42");
    expect(result.current.data?.items[0]?.file.file_name).toBe("Recent.pdf");
  });

  it("supports an empty backend response", async () => {
    const { client } = createClient({
      items: [],
      page_number: 1,
      page_size: 20,
      total: 0,
      has_more: false,
    });
    const { result } = renderHookWithProviders(() => useRecentAccess(client));

    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(result.current.data?.items).toEqual([]);
  });

  it("keeps only the latest record for each file id", async () => {
    const duplicateFile = recentList.items[0]!.file;
    const { client } = createClient({
      items: [
        {
          id: 42,
          file_id: "file-42",
          accessed_at: "2026-09-28T08:00:00Z",
          file: duplicateFile,
        },
        {
          id: 41,
          file_id: "file-42",
          accessed_at: "2026-09-27T08:00:00Z",
          file: duplicateFile,
        },
      ],
      page_number: 1,
      page_size: 20,
      total: 2,
      has_more: false,
    });
    const { result } = renderHookWithProviders(() => useRecentAccess(client));

    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(result.current.data?.items).toHaveLength(1);
    expect(result.current.data?.items[0]?.recordId).toBe(42);
    expect(result.current.data?.items[0]?.accessedAt).toBe("2026-09-28T08:00:00Z");
  });

  it("deletes records sequentially and invalidates the list", async () => {
    let list = { ...recentList };
    const transport = vi.fn(async (_method: string, path: string): Promise<RawResponse> => {
      if (path === "/api/v1/recent/42") {
        list = { ...list, items: [], total: 0 };
        return { status: 200, body: JSON.stringify({ status: "success", data: null, error: null }) };
      }
      return { status: 200, body: JSON.stringify({ status: "success", data: list, error: null }) };
    });
    const client = new ApiClient(transport);
    const { result } = renderHookWithProviders(() => useRecentAccess(client));

    await waitFor(() => expect(result.current.data?.items.length).toBe(1));
    await result.current.deleteRecords.mutateAsync([42]);
    await waitFor(() => expect(result.current.data?.items.length).toBe(0));
    expect(transport).toHaveBeenNthCalledWith(2, "DELETE", "/api/v1/recent/42", undefined);
  });
});

describe("useRecordRecentAccess", () => {
  it("sends one access record request and refreshes the list", async () => {
    const transport = vi.fn(async (): Promise<RawResponse> => ({
      status: 200,
      body: JSON.stringify({ status: "success", data: null, error: null }),
    }));
    const client = new ApiClient(transport);
    const { result } = renderHookWithProviders(() => useRecordRecentAccess(client));

    const response = await result.current.mutateAsync("file-42");

    expect(response.status).toBe("success");
    expect(transport).toHaveBeenCalledTimes(1);
    expect(transport).toHaveBeenCalledWith("POST", "/api/v1/recent", JSON.stringify({ file_id: "file-42" }));
  });
});
