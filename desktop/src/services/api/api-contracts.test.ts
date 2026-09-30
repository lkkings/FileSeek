import { describe, expect, it, vi } from "vitest";

import { ApiClient, type RawResponse } from "./client";
import { addFilesToRecycle, deleteRecycleBatch, listRecycle } from "./recycle";
import { moveFilesToFolder } from "./library";
import { addRecent, deleteRecentRecord, listRecent } from "./recent";
import { warmupSearch } from "./search";
import { deleteTask, listTasks, retryTask } from "./tasks";

function createClient() {
  const transport = vi.fn(async (): Promise<RawResponse> => ({
    status: 200,
    body: JSON.stringify({ status: "success", data: null, error: null }),
  }));
  return { client: new ApiClient(transport), transport };
}

describe("API client", () => {
  it("serializes DELETE bodies through the shared client", async () => {
    const { client, transport } = createClient();

    await client.delete("/recycle", { item_ids: ["item-1"] });

    expect(transport).toHaveBeenCalledWith("DELETE", "/api/v1/recycle", JSON.stringify({ item_ids: ["item-1"] }));
  });
});

describe("Recent API services", () => {
  it("uses the paginated recent list route", async () => {
    const { client, transport } = createClient();

    await listRecent(2, 25, client);

    expect(transport).toHaveBeenCalledWith("GET", "/api/v1/recent?page=2&page_size=25", undefined);
  });

  it("records access and deletes one backend record", async () => {
    const { client, transport } = createClient();

    await addRecent("file-1", client);
    await deleteRecentRecord(42, client);

    expect(transport).toHaveBeenNthCalledWith(1, "POST", "/api/v1/recent", JSON.stringify({ file_id: "file-1" }));
    expect(transport).toHaveBeenNthCalledWith(2, "DELETE", "/api/v1/recent/42", undefined);
  });
});

describe("Recycle API services", () => {
  it("lists, deletes, and moves files with backend payloads", async () => {
    const { client, transport } = createClient();

    await listRecycle(3, 15, client);
    await deleteRecycleBatch(["item-1", "item-2"], client);
    await addFilesToRecycle(["file-1", "file-2"], client);

    expect(transport).toHaveBeenNthCalledWith(1, "GET", "/api/v1/recycle?page=3&page_size=15", undefined);
    expect(transport).toHaveBeenNthCalledWith(2, "DELETE", "/api/v1/recycle", JSON.stringify({ item_ids: ["item-1", "item-2"] }));
    expect(transport).toHaveBeenNthCalledWith(3, "POST", "/api/v1/recycle", JSON.stringify({ file_ids: ["file-1", "file-2"] }));
  });
});

describe("Library API services", () => {
  it("moves files with the backend payload", async () => {
    const { client, transport } = createClient();

    await moveFilesToFolder({ fileIds: ["file-1", "file-2"], targetFolderId: "folder-2" }, client);

    expect(transport).toHaveBeenCalledWith(
      "POST",
      "/api/v1/library/files/move",
      JSON.stringify({ file_ids: ["file-1", "file-2"], target_folder_id: "folder-2" }),
    );
  });
});

describe("Tasks API services", () => {
  it("builds the filtered task query, retry path, and delete path", async () => {
    const { client, transport } = createClient();

    await listTasks("processing", 2, 25, client);
    await retryTask("task/1", client);
    await deleteTask("task/1", client);

    expect(transport).toHaveBeenNthCalledWith(1, "GET", "/api/v1/tasks?page=2&page_size=25&status=processing", undefined);
    expect(transport).toHaveBeenNthCalledWith(2, "POST", "/api/v1/tasks/task%2F1/retry", undefined);
    expect(transport).toHaveBeenNthCalledWith(3, "DELETE", "/api/v1/tasks/task%2F1", undefined);
  });
});

describe("Search API services", () => {
  it("posts to the warmup route without a body", async () => {
    const { client, transport } = createClient();

    await warmupSearch(client);

    expect(transport).toHaveBeenCalledWith("POST", "/api/v1/search/warmup", undefined);
  });
});
