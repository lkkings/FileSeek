import { waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ApiClient, type RawResponse } from "../../../services/api/client";
import type { RecycleListResponse } from "../../../services/api/recycle";
import { useRecycleBin } from "./useRecycleBin";
import { useMoveFilesToRecycle } from "./useMoveFilesToRecycle";
import { renderHookWithProviders } from "../../../test/test-utils";

const firstPage: RecycleListResponse = {
  items: [
    {
      id: "item-1",
      original_file_id: "file-1",
      original_name: "Deleted.pdf",
      original_path: "/documents/Deleted.pdf",
      deleted_at: "2026-09-28T08:00:00Z",
      file_type: "pdf",
      size: "1024",
    },
  ],
  page_number: 1,
  page_size: 20,
  total: 1,
  has_more: false,
};

const emptyPage: RecycleListResponse = {
  items: [],
  page_number: 1,
  page_size: 20,
  total: 0,
  has_more: false,
};

function createRecycleClient() {
  let page = firstPage;
  const transport = vi.fn(async (method: string, path: string): Promise<RawResponse> => {
    if (method === "DELETE" && path === "/api/v1/recycle") {
      page = emptyPage;
      return { status: 200, body: JSON.stringify({ status: "success", data: null, error: null }) };
    }
    if (method === "POST" && path === "/api/v1/recycle/restore") {
      page = emptyPage;
      return { status: 200, body: JSON.stringify({ status: "success", data: null, error: null }) };
    }
    if (method === "POST" && path === "/api/v1/recycle") {
      return { status: 200, body: JSON.stringify({ status: "success", data: null, error: null }) };
    }
    return { status: 200, body: JSON.stringify({ status: "success", data: page, error: null }) };
  });
  return { client: new ApiClient(transport), transport };
}

describe("useRecycleBin", () => {
  it("permanently deletes with the exact body and refreshes the list", async () => {
    const { client, transport } = createRecycleClient();
    const { result } = renderHookWithProviders(() => useRecycleBin(client));

    await waitFor(() => expect(result.current.data?.items.length).toBe(1));
    const response = await result.current.deleteRecords.mutateAsync(["item-1"]);

    expect(response.status).toBe("success");
    expect(transport).toHaveBeenNthCalledWith(2, "DELETE", "/api/v1/recycle", JSON.stringify({ item_ids: ["item-1"] }));
    await waitFor(() => expect(result.current.data?.items.length).toBe(0));
  });

  it("restores with the exact body and refreshes the list", async () => {
    const { client, transport } = createRecycleClient();
    const { result } = renderHookWithProviders(() => useRecycleBin(client));

    await waitFor(() => expect(result.current.data?.items.length).toBe(1));
    const response = await result.current.restoreRecords.mutateAsync(["item-1"]);

    expect(response.status).toBe("success");
    expect(transport).toHaveBeenNthCalledWith(2, "POST", "/api/v1/recycle/restore", JSON.stringify({ item_ids: ["item-1"] }));
    await waitFor(() => expect(result.current.data?.items.length).toBe(0));
  });
});

describe("useMoveFilesToRecycle", () => {
  it("moves files with the exact body", async () => {
    const transport = vi.fn(async (): Promise<RawResponse> => ({
      status: 200,
      body: JSON.stringify({ status: "success", data: null, error: null }),
    }));
    const client = new ApiClient(transport);
    const { result } = renderHookWithProviders(() => useMoveFilesToRecycle(client));

    const response = await result.current.mutateAsync(["file-1", "file-2"]);

    expect(response.status).toBe("success");
    expect(transport).toHaveBeenCalledWith("POST", "/api/v1/recycle", JSON.stringify({ file_ids: ["file-1", "file-2"] }));
  });
});
