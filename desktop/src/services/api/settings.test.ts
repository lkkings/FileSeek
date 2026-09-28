import { describe, expect, it, vi } from "vitest";

import { ApiClient, type RawResponse } from "./client";
import {
  createStorageLocation,
  deleteStorageLocation,
  listClassifierLabels,
  listStorageLocations,
  listStorageDirectory,
  replaceClassifierLabels,
  testStorageLocation,
} from "./settings";

function createClient() {
  const transport = vi.fn(async (): Promise<RawResponse> => ({
    status: 200,
    body: JSON.stringify({ status: "success", data: null, error: null }),
  }));
  return { client: new ApiClient(transport), transport };
}

describe("settings API service", () => {
  it("requests labels and locations without request bodies", async () => {
    const { client, transport } = createClient();
    await listClassifierLabels(client);
    await listStorageLocations(client);

    expect(transport).toHaveBeenNthCalledWith(1, "GET", "/api/v1/settings/classifier-labels", undefined);
    expect(transport).toHaveBeenNthCalledWith(2, "GET", "/api/v1/settings/storage-locations", undefined);
  });

  it("requests a storage directory with an encoded path", async () => {
    const { client, transport } = createClient();
    await listStorageDirectory("nas 1", "Documents/Reports", client);

    expect(transport).toHaveBeenCalledWith(
      "GET",
      "/api/v1/settings/storage-locations/nas%201/directory?path=Documents%2FReports",
      undefined,
    );
  });

  it("replaces labels without sending the response-only version", async () => {
    const { client, transport } = createClient();
    await replaceClassifierLabels({
      document_labels: ["合同"],
      image_labels: ["风景"],
      video_labels: ["会议"],
      version: "client-version",
    }, client);

    expect(transport).toHaveBeenCalledWith(
      "PUT",
      "/api/v1/settings/classifier-labels",
      JSON.stringify({
        document_labels: ["合同"],
        image_labels: ["风景"],
        video_labels: ["会议"],
      }),
    );
  });

  it("maps storage deletion and connection-test requests", async () => {
    const { client, transport } = createClient();
    await createStorageLocation({
      id: "nas1",
      name: "NAS 1",
      protocol: "mounted",
      endpoint: "/Volumes/nas1",
      account: "user",
      password: "secret",
    }, client);
    await deleteStorageLocation("nas1", client);
    await testStorageLocation("nas1", client);

    expect(transport).toHaveBeenNthCalledWith(
      1,
      "POST",
      "/api/v1/settings/storage-locations",
      JSON.stringify({
        id: "nas1",
        name: "NAS 1",
        protocol: "mounted",
        endpoint: "/Volumes/nas1",
        account: "user",
        password: "secret",
      }),
    );
    expect(transport).toHaveBeenNthCalledWith(2, "DELETE", "/api/v1/settings/storage-locations/nas1", undefined);
    expect(transport).toHaveBeenNthCalledWith(3, "POST", "/api/v1/settings/storage-locations/nas1/test", undefined);
  });
});
