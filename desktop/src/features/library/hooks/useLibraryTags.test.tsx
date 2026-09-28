import { waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ApiClient, type RawResponse } from "../../../services/api/client";
import { renderHookWithProviders } from "../../../test/test-utils";
import { useLibraryTags } from "./useLibraryTags";

describe("useLibraryTags", () => {
  it("requests the tag list", async () => {
    const transport = vi.fn(async (): Promise<RawResponse> => ({
      status: 200,
      body: JSON.stringify({ status: "success", data: ["旅游", "攻略"], error: null }),
    }));
    const client = new ApiClient(transport);
    const { result } = renderHookWithProviders(() => useLibraryTags(client));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.tags).toEqual(["旅游", "攻略"]);
    expect(transport).toHaveBeenCalledWith("GET", "/api/v1/library/tags", undefined);
  });

  it("returns a readable error", async () => {
    const transport = vi.fn(async (): Promise<RawResponse> => ({
      status: 200,
      body: JSON.stringify({ status: "error", data: null, error: "标签读取失败" }),
    }));
    const client = new ApiClient(transport);
    const { result } = renderHookWithProviders(() => useLibraryTags(client));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.tags).toEqual(["文档", "图片", "视频"]);
    expect(result.current.error).toBe("标签读取失败");
  });
});
