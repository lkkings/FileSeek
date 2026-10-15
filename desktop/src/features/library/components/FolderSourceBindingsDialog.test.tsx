import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { activateLocale, defaultLocale } from "../../../i18n/i18n";
import { renderWithProviders } from "../../../test/test-utils";
import type { StorageLocation } from "../../settings/types";
import { FolderSourceBindingsDialog } from "./FolderSourceBindingsDialog";

const storageLocations: StorageLocation[] = [
  {
    id: "local",
    type: "local",
    name: "本地存储",
    protocol: "file",
    endpoint: "file://localhost",
    root_path: "/",
    account: null,
    status: "active",
    is_system: true,
  },
  {
    id: "nas",
    type: "nas",
    name: "家庭 NAS",
    protocol: "mounted",
    endpoint: "/Volumes/nas",
    root_path: "/Volumes/nas",
    account: null,
    status: "active",
    is_system: false,
  },
];

const binding = {
  id: "binding-1",
  folder_id: "folder-1",
  storage_id: "nas",
  source_path: "documents",
  recursive: true,
  enabled: true,
  watch_status: "watching",
  last_error: null,
  last_error_at: null,
};

function successResponse(data: unknown) {
  return new Response(JSON.stringify({ status: "success", data, error: null }), {
    status: 200,
  });
}

function directoryResponse(locationId: string, path: string) {
  if (locationId === "nas") {
    return successResponse({
      current_path: path,
      entries: [
        {
          name: "Photos",
          kind: "directory",
          source_path: "Photos",
          size: 0,
          modified: "2026-01-01T00:00:00Z",
        },
      ],
    });
  }
  return successResponse({
    current_path: path,
    entries: path === "/documents"
      ? []
      : [
        {
          name: "documents",
          kind: "directory",
          source_path: "/documents",
          size: 0,
          modified: "2026-01-01T00:00:00Z",
        },
      ],
  });
}

function createFetchMock() {
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input);
    const method = init?.method ?? "GET";
    if (method === "GET" && path.includes("/library/folders/folder-1/source-bindings")) {
      return successResponse([binding]);
    }
    if (method === "GET" && path.includes("/settings/storage-locations/")) {
      const locationId = path.includes("/nas/") ? "nas" : "local";
      const requestedPath = new URL(path, "http://localhost").searchParams.get("path") ?? "";
      return directoryResponse(locationId, requestedPath);
    }
    return successResponse(binding);
  });
}

function renderDialog(onClose = vi.fn()) {
  return renderWithProviders(
    <FolderSourceBindingsDialog
      folderId="folder-1"
      folderName="工作资料"
      storageLocations={storageLocations}
      onClose={onClose}
    />,
  );
}

describe("FolderSourceBindingsDialog", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", createFetchMock());
    activateLocale(defaultLocale);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    activateLocale(defaultLocale);
  });

  it("renders bindings, toggles one, and deletes one", async () => {
    const fetchMock = vi.mocked(fetch);
    renderDialog();

    expect(await screen.findByText("家庭 NAS")).toBeInTheDocument();
    expect(await screen.findByText("监听中")).toBeInTheDocument();
    expect(screen.getAllByText("documents").length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("checkbox", { name: "启用" }));
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/v1/library/folders/folder-1/source-bindings/binding-1",
        expect.objectContaining({
          method: "PATCH",
          body: JSON.stringify({
            storage_id: "nas",
            path: "documents",
            recursive: true,
            enabled: false,
          }),
        }),
      ),
    );

    fireEvent.click(screen.getByRole("button", { name: "删除" }));
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/v1/library/folders/folder-1/source-bindings/binding-1",
        expect.objectContaining({ method: "DELETE" }),
      ),
    );
  });

  it("switches storage sources, navigates directories, and creates a binding", async () => {
    const fetchMock = vi.mocked(fetch);
    renderDialog();

    fireEvent.click(await screen.findByRole("tab", { name: "家庭 NAS" }));
    fireEvent.click(await screen.findByRole("button", { name: "Photos" }));
    fireEvent.click(screen.getByRole("tab", { name: "本地存储" }));
    fireEvent.click(await screen.findByRole("button", { name: "documents" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "包含子目录" }));
    fireEvent.click(screen.getByRole("button", { name: "绑定当前目录" }));

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/v1/library/folders/folder-1/source-bindings",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            storage_id: "local",
            path: "/documents",
            recursive: false,
            enabled: true,
          }),
        }),
      ),
    );
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/settings/storage-locations/nas/directory?path=",
      expect.objectContaining({ method: "GET" }),
    );
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/settings/storage-locations/local/directory?path=%2Fdocuments",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("renders binding health errors without credentials", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        successResponse([
          {
            ...binding,
            watch_status: "error",
            last_error: "来源目录不可访问",
          },
        ]),
      ),
    );
    renderDialog();

    expect(await screen.findByText("出现错误")).toBeInTheDocument();
    expect(screen.getByText("来源目录不可访问")).toBeInTheDocument();
    expect(screen.queryByText("secret")).not.toBeInTheDocument();
  });
});
