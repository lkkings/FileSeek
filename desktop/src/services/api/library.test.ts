import { describe, expect, it, vi } from "vitest";

import { ApiClient, type RawResponse } from "./client";
import { createFolder, startBatchImport, updateFolder } from "./library";

function createClient() {
  const transport = vi.fn(async (): Promise<RawResponse> => ({
    status: 200,
    body: JSON.stringify({ status: "success", data: { file_id: "file-1" }, error: null }),
  }));
  return { client: new ApiClient(transport), transport };
}

describe("library API service", () => {
  it("starts a batch import with default local storage", async () => {
    const { client, transport } = createClient();
    await startBatchImport(
      { folderId: "folder-1", items: [{ path: "/tmp/report.pdf" }] },
      client,
    );

    expect(transport).toHaveBeenCalledWith(
      "POST",
      "/api/v1/library/files/import",
      JSON.stringify({
        folder_id: "folder-1",
        items: [{ path: "/tmp/report.pdf", storage_id: "local" }],
      }),
    );
  });

  it("sends selected storage locations for every item", async () => {
    const { client, transport } = createClient();
    await startBatchImport(
      {
        folderId: "folder-1",
        items: [
          { path: "/Volumes/nas1/report.pdf", storageId: "nas1" },
          { path: "/tmp/local.pdf" },
        ],
      },
      client,
    );

    expect(transport).toHaveBeenCalledWith(
      "POST",
      "/api/v1/library/files/import",
      JSON.stringify({
        folder_id: "folder-1",
        items: [
          { path: "/Volumes/nas1/report.pdf", storage_id: "nas1" },
          { path: "/tmp/local.pdf", storage_id: "local" },
        ],
      }),
    );
  });

  it("sends create and update folder payloads using backend field names", async () => {
    const { client, transport } = createClient();
    const input = { name: "test", iconType: "travel", description: "测试文件夹" };

    await createFolder(input, client);
    await updateFolder("folder-1", input, client);

    expect(transport).toHaveBeenNthCalledWith(
      1,
      "POST",
      "/api/v1/library/folders",
      JSON.stringify({ name: "test", icon_type: "travel", description: "测试文件夹" }),
    );
    expect(transport).toHaveBeenNthCalledWith(
      2,
      "PUT",
      "/api/v1/library/folders/folder-1",
      JSON.stringify({ name: "test", icon_type: "travel", description: "测试文件夹" }),
    );
  });
});
