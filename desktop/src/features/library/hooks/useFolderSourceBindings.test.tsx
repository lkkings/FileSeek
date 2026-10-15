import { waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ApiClient, type RawResponse } from "../../../services/api/client";
import { renderHookWithProviders } from "../../../test/test-utils";
import { useFolderSourceBindings } from "./useFolderSourceBindings";

const apiBinding = {
  id: "binding-1",
  folder_id: "folder-1",
  storage_id: "nas1",
  source_path: "documents",
  recursive: true,
  enabled: true,
  watch_status: "watching",
  last_error: null,
  last_error_at: null,
};

function successResponse(data: unknown): RawResponse {
  return {
    status: 200,
    body: JSON.stringify({ status: "success", data, error: null }),
  };
}

describe("useFolderSourceBindings", () => {
  it("loads and maps folder source bindings", async () => {
    const transport = vi.fn(async (): Promise<RawResponse> => successResponse([apiBinding]));
    const client = new ApiClient(transport);
    const { result } = renderHookWithProviders(() =>
      useFolderSourceBindings("folder-1", client),
    );

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.bindings).toEqual([
      {
        id: "binding-1",
        folderId: "folder-1",
        storageId: "nas1",
        sourcePath: "documents",
        recursive: true,
        enabled: true,
        watchStatus: "watching",
        lastError: null,
        lastErrorAt: null,
      },
    ]);
    expect(transport).toHaveBeenCalledWith(
      "GET",
      "/api/v1/library/folders/folder-1/source-bindings",
      undefined,
    );
  });

  it("creates a binding and invalidates the folder binding query", async () => {
    const transport = vi.fn(async (method: string): Promise<RawResponse> => {
      if (method === "POST") return successResponse(apiBinding);
      return successResponse([apiBinding]);
    });
    const client = new ApiClient(transport);
    const { result } = renderHookWithProviders(() =>
      useFolderSourceBindings("folder-1", client),
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    const error = await result.current.createBinding({
      storageId: "nas1",
      path: "documents",
      recursive: true,
      enabled: true,
    });

    expect(error).toBeNull();
    expect(transport).toHaveBeenNthCalledWith(
      2,
      "POST",
      "/api/v1/library/folders/folder-1/source-bindings",
      JSON.stringify({
        storage_id: "nas1",
        path: "documents",
        recursive: true,
        enabled: true,
      }),
    );
    await waitFor(() => expect(transport).toHaveBeenCalledTimes(3));
    expect(transport).toHaveBeenLastCalledWith(
      "GET",
      "/api/v1/library/folders/folder-1/source-bindings",
      undefined,
    );
  });

  it("returns a readable mutation error", async () => {
    const transport = vi.fn(async (): Promise<RawResponse> => ({
      status: 200,
      body: JSON.stringify({
        status: "error",
        data: null,
        error: "来源目录重叠",
      }),
    }));
    const client = new ApiClient(transport);
    const { result } = renderHookWithProviders(() =>
      useFolderSourceBindings("folder-1", client),
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    const error = await result.current.createBinding({
      storageId: "nas1",
      path: "documents",
      recursive: true,
      enabled: true,
    });

    expect(error).toBe("来源目录重叠");
  });
});
